from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..inference import CircuitPoint, assign_nearest_segment
from ..openf1 import OpenF1HistoricalClient, OpenF1Location, OpenF1RequestError, SessionDiscoveryQuery
from ..replay.controller import (
    FixtureNotFoundError,
    FixtureReplayController,
    ReplayCoordinateBounds,
    ReplayFixtureSummary,
    ReplayLocationPoint,
    ReplayStateSnapshot,
)
from ..settings import get_app_settings
from ..state.track_model import (
    BAHRAIN_MAP_HEIGHT,
    BAHRAIN_MAP_PADDING,
    BAHRAIN_MAP_WIDTH,
    BAHRAIN_SEGMENT_PATHS,
    BAHRAIN_TRACK_SEGMENTS,
)
from ..state import TrackSnapshot, TrackStateReducer

router = APIRouter(prefix="/api/v1", tags=["replay"])

SSE_STREAM_INTERVAL_SECONDS = 0.25
SEED_DRIVER_NUMBERS: tuple[int, ...] = (1, 11, 14, 16, 44)


class FixturesResponse(BaseModel):
    fixtures: list[ReplayFixtureSummary]


class ReplayStartPathRequest(BaseModel):
    speed_multiplier: int = Field(default=1)


class ReplayStateResponse(BaseModel):
    fixture_id: str
    status: str
    speed_multiplier: int
    cursor: int
    total_points: int
    progress_pct: float
    replay_time: str | None
    active_location: ReplayLocationPoint | None
    coordinate_bounds: ReplayCoordinateBounds | None
    timeline_points: list[ReplayLocationPoint]


class ReplayStartBody(BaseModel):
    fixture_id: str = Field(default="bahrain-2023-race")
    speed_multiplier: int = Field(default=1)


class ReplayStatusResponse(BaseModel):
    fixture_id: str
    status: str
    speed_multiplier: int
    cursor: int
    total_points: int
    progress_pct: float
    replay_time: str | None
    message: str


class TrackStateLatestResponse(BaseModel):
    snapshot: TrackSnapshot


class FixtureManifestModel(BaseModel):
    fixture_id: str
    fixture_version: int | None = None
    source: str | None = None
    seed_query: dict[str, Any] = Field(default_factory=dict)
    drivers: list[int] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=list)
    sampling: dict[str, Any] = Field(default_factory=dict)


class FixtureManifestResponse(BaseModel):
    fixture_id: str
    manifest: FixtureManifestModel


def _controller(request: Request) -> FixtureReplayController:
    controller = getattr(request.app.state, "replay_controller", None)
    if controller is None:
        controller = FixtureReplayController(get_app_settings(request))
        request.app.state.replay_controller = controller
    return controller


def _build_openf1_client(request: Request) -> OpenF1HistoricalClient:
    settings = get_app_settings(request)
    return OpenF1HistoricalClient(
        base_url=settings.openf1_base_url,
        mode=settings.openf1_mode,
        bearer_token=settings.openf1_bearer_token,
        timeout_seconds=settings.openf1_timeout_seconds,
        max_retries=settings.openf1_max_retries,
        fixture_data_dir=settings.openf1_fixture_data_dir,
    )


async def _discover_cached_seed_session_key(
    request: Request,
    client: OpenF1HistoricalClient,
) -> int:
    cached_session_key = getattr(request.app.state, "cached_session_key", None)
    if isinstance(cached_session_key, int):
        return cached_session_key

    settings = get_app_settings(request)
    session = await client.discover_session(
        SessionDiscoveryQuery(
            year=settings.openf1_seed_year,
            country_name=settings.openf1_seed_country_name,
            session_name=settings.openf1_seed_session_name,
        )
    )
    request.app.state.cached_session_key = session.session_key
    return session.session_key


def _state_payload(snapshot: ReplayStateSnapshot) -> ReplayStateResponse:
    return ReplayStateResponse(
        fixture_id=snapshot.fixture_id,
        status=snapshot.status,
        speed_multiplier=snapshot.speed_multiplier,
        cursor=snapshot.cursor,
        total_points=snapshot.total_points,
        progress_pct=snapshot.progress_pct,
        replay_time=snapshot.replay_time,
        active_location=snapshot.active_location,
        coordinate_bounds=snapshot.coordinate_bounds,
        timeline_points=snapshot.timeline_points,
    )


def _status_payload(snapshot: ReplayStateSnapshot, *, message: str) -> ReplayStatusResponse:
    return ReplayStatusResponse(
        fixture_id=snapshot.fixture_id,
        status=snapshot.status,
        speed_multiplier=snapshot.speed_multiplier,
        cursor=snapshot.cursor,
        total_points=snapshot.total_points,
        progress_pct=snapshot.progress_pct,
        replay_time=snapshot.replay_time,
        message=message,
    )


def _fixture_exists(controller: FixtureReplayController, fixture_id: str) -> bool:
    return any(item.fixture_id == fixture_id for item in controller.list_fixtures())


def _read_fixture_manifest(settings_dir: str, fixture_id: str) -> FixtureManifestModel:
    fixture_data_dir = Path(settings_dir)
    fixture_root = fixture_data_dir.parent if fixture_data_dir.name in {"golden", "dev", "full"} else fixture_data_dir

    for filename in ("manifest.json", "manifest.template.json"):
        manifest_path = fixture_root / filename
        if manifest_path.exists():
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if payload.get("fixture_id") != fixture_id:
                raise FixtureNotFoundError(f"Fixture '{fixture_id}' was not found")
            return FixtureManifestModel.model_validate(payload)

    raise FileNotFoundError(
        f"Fixture '{fixture_id}' manifest was not found under '{fixture_root}'"
    )


def _track_snapshot_from_replay(snapshot: ReplayStateSnapshot) -> TrackSnapshot:
    reducer = TrackStateReducer(fixture_id=snapshot.fixture_id)

    if snapshot.active_weather is not None:
        reducer.apply_event(
            {
                "fixture_id": snapshot.fixture_id,
                "event_type": "weather",
                "occurred_at": snapshot.active_weather.occurred_at,
                "payload": {
                    "track_temperature": snapshot.active_weather.track_temperature,
                    "air_temperature": snapshot.active_weather.air_temperature,
                    "humidity": snapshot.active_weather.humidity,
                    "pressure": snapshot.active_weather.pressure,
                    "rainfall": snapshot.active_weather.rainfall,
                    "wind_direction": snapshot.active_weather.wind_direction,
                    "wind_speed": snapshot.active_weather.wind_speed,
                },
            }
        )

    if snapshot.total_points > 0 and snapshot.timeline_points:
        max_index = min(snapshot.cursor, len(snapshot.timeline_points) - 1)
        for idx in range(max_index + 1):
            point = snapshot.timeline_points[idx]
            normalized_progress = idx / max(1, len(snapshot.timeline_points) - 1)
            segment_id = _assign_segment_for_location(point, snapshot.coordinate_bounds)
            if segment_id is None:
                segment_id = _segment_id_from_progress(normalized_progress)

            reducer.apply_event(
                {
                    "fixture_id": snapshot.fixture_id,
                    "event_type": "location",
                    "driver_number": point.driver_number,
                    "occurred_at": point.occurred_at,
                    "payload": {
                        "driver_number": point.driver_number,
                        "x": point.x,
                        "y": point.y,
                        "date": point.occurred_at,
                        "segment_id": segment_id,
                        "normalized_progress": normalized_progress,
                    },
                }
            )

    reducer.apply_event(
        {
            "fixture_id": snapshot.fixture_id,
            "event_type": "replay.status",
            "status": snapshot.status,
            "occurred_at": snapshot.replay_time,
            "payload": {"status": snapshot.status},
        }
    )
    return reducer.snapshot()


def _sort_locations(records: list[OpenF1Location]) -> list[OpenF1Location]:
    return sorted(records, key=lambda record: (record.date, record.driver_number))


def _coordinate_bounds_from_locations(records: list[OpenF1Location]) -> ReplayCoordinateBounds | None:
    if not records:
        return None

    xs = [record.x for record in records]
    ys = [record.y for record in records]
    return ReplayCoordinateBounds(
        min_x=min(xs),
        max_x=max(xs),
        min_y=min(ys),
        max_y=max(ys),
    )


async def _track_snapshot_from_historical(
    request: Request,
    replay_snapshot: ReplayStateSnapshot,
) -> TrackSnapshot:
    client = _build_openf1_client(request)
    session_key = await _discover_cached_seed_session_key(request, client)

    weather_records = await client.get_weather(session_key=session_key, limit=1)
    location_batches = await client.get_location_batch(
        session_key=session_key,
        driver_numbers=SEED_DRIVER_NUMBERS,
        limit=5,
    )

    location_records = _sort_locations(
        [record for records in location_batches.values() for record in records]
    )
    coordinate_bounds = _coordinate_bounds_from_locations(location_records)

    reducer = TrackStateReducer(fixture_id=replay_snapshot.fixture_id)
    latest_weather = weather_records[0] if weather_records else None
    if latest_weather is not None:
        reducer.apply_event(
            {
                "fixture_id": replay_snapshot.fixture_id,
                "session_key": session_key,
                "event_type": "weather",
                "occurred_at": latest_weather.date.isoformat(),
                "payload": {
                    "track_temperature": latest_weather.track_temperature,
                    "air_temperature": latest_weather.air_temperature,
                    "humidity": latest_weather.humidity,
                    "pressure": latest_weather.pressure,
                    "rainfall": latest_weather.rainfall,
                    "wind_direction": latest_weather.wind_direction,
                    "wind_speed": latest_weather.wind_speed,
                },
            }
        )

    total_records = len(location_records)
    for index, record in enumerate(location_records):
        mapped_point = (
            _project_location_to_map(
                x=record.x,
                y=record.y,
                coordinate_bounds=coordinate_bounds,
            )
            if coordinate_bounds is not None
            else CircuitPoint(x=record.x, y=record.y)
        )
        segment_id = assign_nearest_segment(point=mapped_point, segments=BAHRAIN_SEGMENT_PATHS).segment_id
        normalized_progress = 0.0 if total_records <= 1 else index / max(1, total_records - 1)

        reducer.apply_event(
            {
                "fixture_id": replay_snapshot.fixture_id,
                "session_key": session_key,
                "event_type": "location",
                "driver_number": record.driver_number,
                "occurred_at": record.date.isoformat(),
                "payload": {
                    "driver_number": record.driver_number,
                    "x": mapped_point.x,
                    "y": mapped_point.y,
                    "z": record.z,
                    "date": record.date.isoformat(),
                    "segment_id": segment_id,
                    "normalized_progress": normalized_progress,
                },
            }
        )

    reducer.apply_event(
        {
            "fixture_id": replay_snapshot.fixture_id,
            "session_key": session_key,
            "event_type": "replay.status",
            "status": replay_snapshot.status,
            "occurred_at": replay_snapshot.replay_time,
            "payload": {
                "status": replay_snapshot.status,
                "connection_status": "connected",
            },
        }
    )
    return reducer.snapshot()


def _project_location_to_map(
    *,
    x: float,
    y: float,
    coordinate_bounds: ReplayCoordinateBounds,
) -> CircuitPoint:
    x_span = max(1.0, coordinate_bounds.max_x - coordinate_bounds.min_x)
    y_span = max(1.0, coordinate_bounds.max_y - coordinate_bounds.min_y)
    map_width = max(1.0, BAHRAIN_MAP_WIDTH - (BAHRAIN_MAP_PADDING * 2))
    map_height = max(1.0, BAHRAIN_MAP_HEIGHT - (BAHRAIN_MAP_PADDING * 2))

    normalized_x = (x - coordinate_bounds.min_x) / x_span
    normalized_y = (y - coordinate_bounds.min_y) / y_span

    return CircuitPoint(
        x=float(BAHRAIN_MAP_PADDING + (normalized_x * map_width)),
        y=float(BAHRAIN_MAP_PADDING + (normalized_y * map_height)),
    )


def _assign_segment_for_location(
    point: ReplayLocationPoint,
    coordinate_bounds: ReplayCoordinateBounds | None,
) -> str | None:
    if coordinate_bounds is None:
        return None

    projected = _project_location_to_map(
        x=point.x,
        y=point.y,
        coordinate_bounds=coordinate_bounds,
    )
    assignment = assign_nearest_segment(point=projected, segments=BAHRAIN_SEGMENT_PATHS)
    return assignment.segment_id


def _segment_id_from_progress(progress: float) -> str:
    clamped = min(1.0, max(0.0, progress))
    segment_count = len(BAHRAIN_TRACK_SEGMENTS)
    index = min(segment_count - 1, int(clamped * segment_count))
    return BAHRAIN_TRACK_SEGMENTS[index].segment_id


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def _track_state_sse_events(
    request: Request,
    controller: FixtureReplayController,
    *,
    max_events: int | None = None,
):
    last_snapshot_json: str | None = None
    emitted_count = 0

    while True:
        if await request.is_disconnected():
            break

        replay_snapshot = controller.snapshot()
        snapshot = _track_snapshot_from_replay(replay_snapshot)
        snapshot_json = snapshot.model_dump_json()

        if snapshot_json != last_snapshot_json:
            last_snapshot_json = snapshot_json
            yield _sse_event(
                "track_state",
                {
                    "snapshot": snapshot.model_dump(mode="json"),
                    "event_type": "track_state",
                },
            )
        else:
            yield _sse_event(
                "heartbeat",
                {
                    "fixture_id": replay_snapshot.fixture_id,
                    "replay_status": replay_snapshot.status,
                    "event_type": "heartbeat",
                },
            )

        emitted_count += 1
        if max_events is not None and emitted_count >= max_events:
            break

        await asyncio.sleep(SSE_STREAM_INTERVAL_SECONDS)


@router.get("/fixtures", response_model=FixturesResponse)
async def list_fixtures(
    controller: FixtureReplayController = Depends(_controller),
) -> FixturesResponse:
    return FixturesResponse(fixtures=controller.list_fixtures())


@router.get("/fixtures/{fixture_id}/manifest", response_model=FixtureManifestResponse)
async def fixture_manifest(
    fixture_id: str,
    request: Request,
    controller: FixtureReplayController = Depends(_controller),
) -> FixtureManifestResponse:
    if not _fixture_exists(controller, fixture_id):
        raise HTTPException(status_code=404, detail=f"Fixture '{fixture_id}' was not found")

    settings = get_app_settings(request)
    try:
        manifest = _read_fixture_manifest(settings.openf1_fixture_data_dir, fixture_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FixtureManifestResponse(fixture_id=fixture_id, manifest=manifest)


@router.post("/replay/{fixture_id}/start", response_model=ReplayStatusResponse)
async def start_replay(
    fixture_id: str,
    body: ReplayStartPathRequest,
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayStatusResponse:
    try:
        snapshot = await controller.start(
            fixture_id=fixture_id,
            speed_multiplier=body.speed_multiplier,
        )
    except FixtureNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _status_payload(snapshot, message="Replay started")


@router.post("/replay/{fixture_id}/pause", response_model=ReplayStatusResponse)
async def pause_replay(
    fixture_id: str,
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayStatusResponse:
    if not _fixture_exists(controller, fixture_id):
        raise HTTPException(status_code=404, detail=f"Fixture '{fixture_id}' was not found")
    snapshot = await controller.pause()
    return _status_payload(snapshot, message="Replay paused")


@router.post("/replay/{fixture_id}/stop", response_model=ReplayStatusResponse)
async def stop_replay(
    fixture_id: str,
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayStatusResponse:
    if not _fixture_exists(controller, fixture_id):
        raise HTTPException(status_code=404, detail=f"Fixture '{fixture_id}' was not found")
    snapshot = await controller.stop()
    return _status_payload(snapshot, message="Replay stopped")


@router.get("/events/replay-status", response_model=ReplayStatusResponse)
async def replay_status(
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayStatusResponse:
    return _status_payload(controller.snapshot(), message="Latest replay status")


@router.get("/track-state/latest", response_model=TrackStateLatestResponse)
async def latest_track_state(
    request: Request,
    controller: FixtureReplayController = Depends(_controller),
) -> TrackStateLatestResponse:
    replay_snapshot = controller.snapshot()
    settings = get_app_settings(request)

    if replay_snapshot.status == "running":
        return TrackStateLatestResponse(snapshot=_track_snapshot_from_replay(replay_snapshot))

    if settings.openf1_mode == "historical":
        try:
            snapshot = await _track_snapshot_from_historical(request, replay_snapshot)
        except OpenF1RequestError as exc:
            raise HTTPException(
                status_code=503,
                detail="OpenF1 is currently unavailable while fetching track state data.",
            ) from exc
        return TrackStateLatestResponse(snapshot=snapshot)

    return TrackStateLatestResponse(snapshot=_track_snapshot_from_replay(replay_snapshot))


@router.get("/stream/track-state")
async def stream_track_state(
    request: Request,
    controller: FixtureReplayController = Depends(_controller),
) -> StreamingResponse:
    return StreamingResponse(
        _track_state_sse_events(request, controller),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/replay/fixtures", response_model=FixturesResponse)
async def list_replay_fixtures_legacy(
    controller: FixtureReplayController = Depends(_controller),
) -> FixturesResponse:
    return FixturesResponse(fixtures=controller.list_fixtures())


@router.post("/replay/start", response_model=ReplayStateResponse)
async def start_replay_legacy(
    body: ReplayStartBody,
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayStateResponse:
    try:
        snapshot = await controller.start(
            fixture_id=body.fixture_id,
            speed_multiplier=body.speed_multiplier,
        )
    except FixtureNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _state_payload(snapshot)


@router.post("/replay/stop", response_model=ReplayStateResponse)
async def stop_replay_legacy(
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayStateResponse:
    return _state_payload(await controller.pause())


@router.get("/replay/state", response_model=ReplayStateResponse)
async def replay_state_legacy(
    controller: FixtureReplayController = Depends(_controller),
) -> ReplayStateResponse:
    return _state_payload(controller.snapshot())