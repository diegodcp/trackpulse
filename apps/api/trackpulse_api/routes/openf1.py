from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

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