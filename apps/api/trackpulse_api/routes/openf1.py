from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from ..inference import project_wind_projection
from ..observability import request_id_context
from ..openf1 import (
    OpenF1HistoricalClient,
    OpenF1Location,
    OpenF1RequestError,
    OpenF1Session,
    OpenF1Weather,
    SessionDiscoveryQuery,
    SessionNotFoundError,
)
from ..settings import AppSettings, get_app_settings

router = APIRouter(prefix="/api/v1", tags=["openf1"])

T = TypeVar("T")


class ResponseMeta(BaseModel):
    request_id: str


class ApiResponse(BaseModel, Generic[T]):
    data: T
    meta: ResponseMeta


class ApiError(BaseModel):
    code: str
    message: str


class ApiErrorResponse(BaseModel):
    error: ApiError
    meta: ResponseMeta


class TrackSegmentMeasuredState(BaseModel):
    trackTemperatureC: float | None = None
    airTemperatureC: float | None = None
    windSpeedMs: float | None = None
    windDirectionDeg: int | None = None
    rainfall: bool | None = None


class TrackSegmentDerivedState(BaseModel):
    trafficScore: float | None = None
    windRelativeAngleDeg: float | None = None
    windClass: str | None = None
    windStrengthScore: float | None = None


class TrackSegmentInferredState(BaseModel):
    confidence: float | None = None


class TrackSegmentStateResponse(BaseModel):
    segmentId: str
    sessionKey: int | str
    updatedAt: str
    measured: TrackSegmentMeasuredState
    derived: TrackSegmentDerivedState
    inferred: TrackSegmentInferredState


# Assumption: until a backend-owned track-map contract lands, TP-LAYER-01 uses the
# existing 12-segment fixture circuit IDs and headings to provide stable payloads.
FIXTURE_SEGMENTS: tuple[tuple[str, float], ...] = (
    ("s01", 335.0),
    ("s02", 310.0),
    ("s03", 284.0),
    ("s04", 98.0),
    ("s05", 112.0),
    ("s06", 150.0),
    ("s07", 165.0),
    ("s08", 225.0),
    ("s09", 263.0),
    ("s10", 254.0),
    ("s11", 319.0),
    ("s12", 325.0),
)


def _build_client(settings: AppSettings) -> OpenF1HistoricalClient:
    return OpenF1HistoricalClient(
        base_url=settings.openf1_base_url,
        mode=settings.openf1_mode,
        bearer_token=settings.openf1_bearer_token,
        timeout_seconds=settings.openf1_timeout_seconds,
        max_retries=settings.openf1_max_retries,
        fixture_data_dir=settings.openf1_fixture_data_dir,
    )


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=request_id_context.get())


def _success(data: T) -> ApiResponse[T]:
    return ApiResponse(data=data, meta=_meta())


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    payload = ApiErrorResponse(error=ApiError(code=code, message=message), meta=_meta())
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


async def _discover_seed_session(
    client: OpenF1HistoricalClient,
    settings: AppSettings,
) -> OpenF1Session:
    return await client.discover_session(
        SessionDiscoveryQuery(
            year=settings.openf1_seed_year,
            country_name=settings.openf1_seed_country_name,
            session_name=settings.openf1_seed_session_name,
        )
    )


def _sort_weather_records(records: list[OpenF1Weather]) -> list[OpenF1Weather]:
    return sorted(records, key=lambda record: record.date)


def _sort_location_records(records: list[OpenF1Location]) -> list[OpenF1Location]:
    return sorted(records, key=lambda record: (record.date, record.driver_number))


def _build_track_state_from_weather(weather: OpenF1Weather) -> list[TrackSegmentStateResponse]:
    segment_states: list[TrackSegmentStateResponse] = []

    for index, (segment_id, segment_heading_deg) in enumerate(FIXTURE_SEGMENTS):
        wind_projection = project_wind_projection(
            wind_direction_deg=float(weather.wind_direction) if weather.wind_direction is not None else None,
            wind_speed_ms=weather.wind_speed,
            segment_direction_deg=segment_heading_deg,
        )

        segment_states.append(
            TrackSegmentStateResponse(
                segmentId=segment_id,
                sessionKey="fixture",
                updatedAt=weather.date.isoformat(),
                measured=TrackSegmentMeasuredState(
                    trackTemperatureC=weather.track_temperature,
                    airTemperatureC=weather.air_temperature,
                    windSpeedMs=weather.wind_speed,
                    windDirectionDeg=weather.wind_direction,
                    rainfall=weather.rainfall,
                ),
                derived=TrackSegmentDerivedState(
                    trafficScore=float(min(100, 15 + (index * 7))),
                    windRelativeAngleDeg=wind_projection.relative_angle_deg,
                    windClass=wind_projection.wind_class,
                    windStrengthScore=wind_projection.strength_score,
                ),
                inferred=TrackSegmentInferredState(confidence=0.5),
            )
        )

    return segment_states


def _map_openf1_exception(exc: Exception) -> JSONResponse:
    if isinstance(exc, SessionNotFoundError):
        return _error(404, "openf1_session_not_found", "No OpenF1 session matched the configured seed query.")

    if isinstance(exc, OpenF1RequestError):
        return _error(502, "openf1_request_failed", "The backend could not fetch data from OpenF1.")

    if isinstance(exc, (ValidationError, ValueError, FileNotFoundError)):
        return _error(502, "openf1_payload_invalid", "The backend received an invalid OpenF1 payload.")

    raise exc


@router.get("/sessions/latest", response_model=ApiResponse[OpenF1Session])
async def latest_session(settings: AppSettings = Depends(get_app_settings)) -> ApiResponse[OpenF1Session] | JSONResponse:
    client = _build_client(settings)

    try:
        session = await _discover_seed_session(client, settings)
    except Exception as exc:  # noqa: BLE001
        return _map_openf1_exception(exc)

    return _success(session)


@router.get("/openf1/weather/latest", response_model=ApiResponse[OpenF1Weather])
async def latest_weather(settings: AppSettings = Depends(get_app_settings)) -> ApiResponse[OpenF1Weather] | JSONResponse:
    client = _build_client(settings)

    try:
        session = await _discover_seed_session(client, settings)
        records = _sort_weather_records(await client.get_weather(session_key=session.session_key))
    except Exception as exc:  # noqa: BLE001
        return _map_openf1_exception(exc)

    if not records:
        return _error(404, "openf1_weather_not_found", "No OpenF1 weather records were available.")

    return _success(records[-1])


@router.get("/openf1/location/sample", response_model=ApiResponse[list[OpenF1Location]])
async def location_sample(settings: AppSettings = Depends(get_app_settings)) -> ApiResponse[list[OpenF1Location]] | JSONResponse:
    client = _build_client(settings)

    try:
        session = await _discover_seed_session(client, settings)
        records = _sort_location_records(await client.get_location(session_key=session.session_key))
    except Exception as exc:  # noqa: BLE001
        return _map_openf1_exception(exc)

    return _success(records[:10])


@router.get("/openf1/track-state/latest", response_model=ApiResponse[list[TrackSegmentStateResponse]])
async def latest_track_state(
    settings: AppSettings = Depends(get_app_settings),
) -> ApiResponse[list[TrackSegmentStateResponse]] | JSONResponse:
    client = _build_client(settings)

    try:
        session = await _discover_seed_session(client, settings)
        records = _sort_weather_records(await client.get_weather(session_key=session.session_key))
    except Exception as exc:  # noqa: BLE001
        return _map_openf1_exception(exc)

    if not records:
        return _error(404, "openf1_weather_not_found", "No OpenF1 weather records were available.")

    return _success(_build_track_state_from_weather(records[-1]))