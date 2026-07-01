from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..replay.controller import (
    FixtureNotFoundError,
    FixtureReplayController,
    ReplayCoordinateBounds,
    ReplayFixtureSummary,
    ReplayLocationPoint,
    ReplayStateSnapshot,
)
from ..settings import get_app_settings
from ..state import TrackSnapshot, TrackStateReducer

router = APIRouter(prefix="/api/v1", tags=["replay"])

SSE_STREAM_INTERVAL_SECONDS = 0.25


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
    if snapshot.total_points > 0 and snapshot.timeline_points:
        max_index = min(snapshot.cursor, len(snapshot.timeline_points) - 1)
        for idx in range(max_index + 1):
            point = snapshot.timeline_points[idx]
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
    controller: FixtureReplayController = Depends(_controller),
) -> TrackStateLatestResponse:
    return TrackStateLatestResponse(snapshot=_track_snapshot_from_replay(controller.snapshot()))


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