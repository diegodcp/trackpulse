"""Tests for TP-BH-0004: low-frequency raw endpoint download."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from workers.fixtures import download_openf1
from workers.fixtures.download_openf1 import (
    DriverEndpointResult,
    EndpointResult,
    LOW_FREQUENCY_ENDPOINTS,
    MANDATORY_ENDPOINTS,
    SessionRef,
    _build_summary,
    _decimate_timestamped_records,
    _download_high_frequency,
    _download_low_frequency,
    _fetch_with_retry,
    _write_driver_raw_files,
    _write_raw_files,
    _write_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, body: Any) -> httpx.Response:
    """Build a minimal httpx.Response suitable for use in tests."""
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        request=httpx.Request("GET", "https://api.openf1.org/v1/test"),
    )


def _make_async_client(responses: dict[str, Any]) -> httpx.AsyncClient:
    """Build an AsyncClient whose get() returns pre-canned responses.

    ``responses`` maps endpoint path (e.g. ``"/v1/drivers"``) to either:
    - a list (happy-path records), or
    - an httpx.Response (to simulate error codes), or
    - an Exception (to simulate network failure).
    """
    mock_client = MagicMock(spec=httpx.AsyncClient)

    async def _get(path: str, *, params: dict[str, Any] | None = None, timeout: float = 30.0) -> httpx.Response:
        key = path if path in responses else path.lstrip("/")
        value = responses.get(path) or responses.get(path.lstrip("/"))
        if value is None:
            return _make_response(200, [])
        if isinstance(value, Exception):
            raise value
        if isinstance(value, httpx.Response):
            return value
        # list / dict → success response
        return _make_response(200, value)

    mock_client.get = AsyncMock(side_effect=_get)
    return mock_client


SAMPLE_SESSION_REF = SessionRef(session_key=9149, meeting_key=238)


# ---------------------------------------------------------------------------
# _fetch_with_retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_with_retry_success_first_attempt() -> None:
    records = [{"session_key": 9149, "air_temperature": 29.8}]
    mock_client = _make_async_client({"/v1/weather": records})

    result = await _fetch_with_retry(mock_client, "/v1/weather", {"session_key": 9149})

    assert result == records


@pytest.mark.asyncio
async def test_fetch_with_retry_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(download_openf1, "asyncio", _fake_asyncio())

    records = [{"driver_number": 1}]
    call_count = 0

    async def _get(path: str, *, params: Any = None, timeout: float = 30.0) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return _make_response(429, {"detail": "rate limited"})
        return _make_response(200, records)

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=_get)

    result = await _fetch_with_retry(mock_client, "/v1/drivers", {"session_key": 9149}, max_retries=3)

    assert result == records
    assert call_count == 3


@pytest.mark.asyncio
async def test_fetch_with_retry_retries_on_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(download_openf1, "asyncio", _fake_asyncio())

    call_count = 0

    async def _get(path: str, *, params: Any = None, timeout: float = 30.0) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return _make_response(500, {"detail": "server error"})

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=_get)

    with pytest.raises(RuntimeError, match="Failed to fetch"):
        await _fetch_with_retry(mock_client, "/v1/laps", {"session_key": 9149}, max_retries=2)

    assert call_count == 3  # initial + 2 retries


@pytest.mark.asyncio
async def test_fetch_with_retry_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(download_openf1, "asyncio", _fake_asyncio())

    async def _get(path: str, *, params: Any = None, timeout: float = 30.0) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=_get)

    with pytest.raises(RuntimeError, match="Failed to fetch"):
        await _fetch_with_retry(mock_client, "/v1/laps", {"session_key": 9149}, max_retries=1)


@pytest.mark.asyncio
async def test_fetch_with_retry_raises_on_non_list_payload() -> None:
    async def _get(path: str, *, params: Any = None, timeout: float = 30.0) -> httpx.Response:
        return _make_response(200, {"not": "a list"})

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=_get)

    with pytest.raises(ValueError, match="Expected list"):
        await _fetch_with_retry(mock_client, "/v1/weather", {"session_key": 9149})


# ---------------------------------------------------------------------------
# _download_low_frequency
# ---------------------------------------------------------------------------

def _happy_path_responses() -> dict[str, Any]:
    return {
        "/v1/sessions": [{"session_key": 9149, "session_name": "Race"}],
        "/v1/drivers": [{"driver_number": 1, "full_name": "Max Verstappen"}],
        "/v1/weather": [{"air_temperature": 29.8}],
        "/v1/laps": [{"lap_number": 1, "driver_number": 1}],
        "/v1/intervals": [{"driver_number": 1, "gap_to_leader": 0.0}],
        "/v1/position": [{"driver_number": 1, "position": 1}],
        "/v1/stints": [{"driver_number": 1, "stint_number": 1}],
        "/v1/pit": [{"driver_number": 1, "lap_number": 20}],
        "/v1/race_control": [{"flag": "GREEN", "lap_number": 1}],
    }


@pytest.mark.asyncio
async def test_download_low_frequency_happy_path() -> None:
    mock_client = _make_async_client(_happy_path_responses())

    results = await _download_low_frequency(SAMPLE_SESSION_REF, http_client=mock_client)

    assert len(results) == len(LOW_FREQUENCY_ENDPOINTS)
    for result in results:
        assert result.ok, f"{result.endpoint} failed: {result.error}"
        assert result.count > 0


@pytest.mark.asyncio
async def test_download_low_frequency_uses_session_key() -> None:
    """All low-frequency endpoints should be requested with session_key."""
    calls: list[tuple[str, dict[str, Any]]] = []

    async def _get(path: str, *, params: Any = None, timeout: float = 30.0) -> httpx.Response:
        calls.append((path, params or {}))
        return _make_response(200, [])

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=_get)

    await _download_low_frequency(SAMPLE_SESSION_REF, http_client=mock_client)

    for path, params in calls:
        assert params.get("session_key") == SAMPLE_SESSION_REF.session_key, (
            f"{path} did not use session_key"
        )


@pytest.mark.asyncio
async def test_download_low_frequency_empty_optional_allowed() -> None:
    """Optional endpoints that return empty arrays are OK (no error)."""
    responses = _happy_path_responses()
    responses["/v1/weather"] = []  # empty optional
    responses["/v1/intervals"] = []

    mock_client = _make_async_client(responses)
    results = await _download_low_frequency(SAMPLE_SESSION_REF, http_client=mock_client)

    weather = next(r for r in results if r.endpoint == "weather")
    assert weather.ok
    assert weather.count == 0
    assert not weather.mandatory


@pytest.mark.asyncio
async def test_download_low_frequency_records_error_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed endpoint produces an EndpointResult with error set."""
    monkeypatch.setattr(download_openf1, "asyncio", _fake_asyncio())

    responses = _happy_path_responses()
    # Replace laps with a server error response (always fails)
    async def _get(path: str, *, params: Any = None, timeout: float = 30.0) -> httpx.Response:
        if path == "/v1/laps":
            return _make_response(500, {"detail": "error"})
        return _make_response(200, responses.get(path, []))

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=_get)

    results = await _download_low_frequency(SAMPLE_SESSION_REF, http_client=mock_client)

    laps_result = next(r for r in results if r.endpoint == "laps")
    assert not laps_result.ok
    assert laps_result.error is not None
    assert laps_result.mandatory


# ---------------------------------------------------------------------------
# _build_summary
# ---------------------------------------------------------------------------

def test_build_summary_lists_counts() -> None:
    results = [
        EndpointResult("sessions", [{"session_key": 9149}], mandatory=True),
        EndpointResult("drivers", [{"driver_number": 1}, {"driver_number": 11}], mandatory=True),
        EndpointResult("weather", [], mandatory=False),
        EndpointResult("laps", [{"lap_number": 1}], mandatory=True),
        EndpointResult("intervals", [], mandatory=False, error="timeout"),
    ]

    summary = _build_summary("bahrain-2023-race", SAMPLE_SESSION_REF, results)

    assert summary["fixture_id"] == "bahrain-2023-race"
    assert summary["session_key"] == 9149
    assert summary["meeting_key"] == 238
    assert summary["endpoints"]["sessions"] == 1
    assert summary["endpoints"]["drivers"] == 2
    assert summary["endpoints"]["weather"] == 0
    assert summary["endpoints"]["laps"] == 1
    assert isinstance(summary["endpoints"]["intervals"], dict)
    assert "error" in summary["endpoints"]["intervals"]


def test_build_summary_includes_driver_high_frequency_counts() -> None:
    results = [
        EndpointResult("sessions", [{"session_key": 9149}], mandatory=True),
    ]
    driver_results = [
        DriverEndpointResult(
            endpoint="location",
            driver_number=1,
            records_before=[{"date": "2023-03-05T15:00:00Z"}, {"date": "2023-03-05T15:00:00.400Z"}],
            records_after=[{"date": "2023-03-05T15:00:00Z"}],
        ),
        DriverEndpointResult(
            endpoint="car_data",
            driver_number=1,
            records_before=[],
            records_after=[],
            error="timeout",
        ),
    ]

    summary = _build_summary("bahrain-2023-race", SAMPLE_SESSION_REF, results, driver_results)

    assert summary["high_frequency"]["drivers"]["1"]["location"] == {"before": 2, "after": 1}
    assert "error" in summary["high_frequency"]["drivers"]["1"]["car_data"]


# ---------------------------------------------------------------------------
# High-frequency decimation and download
# ---------------------------------------------------------------------------

def test_decimate_timestamped_records_is_deterministic_and_1hz() -> None:
    records = [
        {"date": "2023-03-05T15:00:00.900Z", "value": "late"},
        {"date": "2023-03-05T15:00:00.100Z", "value": "early"},
        {"date": "2023-03-05T15:00:01.100Z", "value": "next-second"},
        {"date": "2023-03-05T15:00:01.900Z", "value": "drop"},
    ]

    first = _decimate_timestamped_records(records, sample_rate_hz=1)
    second = _decimate_timestamped_records(records, sample_rate_hz=1)

    assert first == second
    assert [row["value"] for row in first] == ["early", "next-second"]


@pytest.mark.asyncio
async def test_download_high_frequency_decimates_for_dev_level() -> None:
    responses = {
        "/v1/location": [
            {"date": "2023-03-05T15:00:00.000Z", "x": 1},
            {"date": "2023-03-05T15:00:00.500Z", "x": 2},
            {"date": "2023-03-05T15:00:01.000Z", "x": 3},
        ],
        "/v1/car_data": [
            {"date": "2023-03-05T15:00:00.010Z", "speed": 300},
            {"date": "2023-03-05T15:00:00.910Z", "speed": 302},
        ],
    }
    mock_client = _make_async_client(responses)

    results = await _download_high_frequency(
        SAMPLE_SESSION_REF,
        [1],
        level="dev",
        http_client=mock_client,
    )

    location = next(r for r in results if r.endpoint == "location")
    car_data = next(r for r in results if r.endpoint == "car_data")

    assert location.count_before == 3
    assert location.count_after == 2
    assert car_data.count_before == 2
    assert car_data.count_after == 1


@pytest.mark.asyncio
async def test_download_high_frequency_preserves_full_level() -> None:
    responses = {
        "/v1/location": [
            {"date": "2023-03-05T15:00:00.000Z"},
            {"date": "2023-03-05T15:00:00.200Z"},
        ],
        "/v1/car_data": [
            {"date": "2023-03-05T15:00:00.300Z"},
            {"date": "2023-03-05T15:00:00.700Z"},
        ],
    }
    mock_client = _make_async_client(responses)

    results = await _download_high_frequency(
        SAMPLE_SESSION_REF,
        [1],
        level="full",
        http_client=mock_client,
    )

    for result in results:
        assert result.count_after == result.count_before


def test_write_driver_raw_files_creates_driver_scoped_files(tmp_path: Path) -> None:
    driver_results = [
        DriverEndpointResult(
            endpoint="location",
            driver_number=1,
            records_before=[{"date": "2023-03-05T15:00:00Z"}],
            records_after=[{"date": "2023-03-05T15:00:00Z"}],
        ),
        DriverEndpointResult(
            endpoint="car_data",
            driver_number=1,
            records_before=[],
            records_after=[],
            error="timeout",
        ),
    ]

    _write_driver_raw_files(tmp_path, driver_results)

    assert (tmp_path / "raw" / "location.driver_1.json").exists()
    assert not (tmp_path / "raw" / "car_data.driver_1.json").exists()


# ---------------------------------------------------------------------------
# _write_raw_files / _write_summary
# ---------------------------------------------------------------------------

def test_write_raw_files_creates_json_files(tmp_path: Path) -> None:
    results = [
        EndpointResult("sessions", [{"session_key": 9149}], mandatory=True),
        EndpointResult("weather", [{"air_temperature": 30.0}], mandatory=False),
        # Failed endpoint — no file should be written
        EndpointResult("laps", [], mandatory=True, error="timeout"),
    ]

    _write_raw_files(tmp_path, results)

    assert (tmp_path / "raw" / "sessions.json").exists()
    assert (tmp_path / "raw" / "weather.json").exists()
    assert not (tmp_path / "raw" / "laps.json").exists()

    sessions_data = json.loads((tmp_path / "raw" / "sessions.json").read_text())
    assert sessions_data == [{"session_key": 9149}]


def test_write_raw_files_creates_raw_dir(tmp_path: Path) -> None:
    results = [EndpointResult("drivers", [{"driver_number": 1}], mandatory=True)]
    _write_raw_files(tmp_path, results)
    assert (tmp_path / "raw").is_dir()


def test_write_summary_creates_file(tmp_path: Path) -> None:
    summary = {
        "fixture_id": "bahrain-2023-race",
        "session_key": 9149,
        "meeting_key": 238,
        "endpoints": {"sessions": 1},
    }
    _write_summary(tmp_path, summary)

    dest = tmp_path / "summary.json"
    assert dest.exists()
    assert json.loads(dest.read_text()) == summary


# ---------------------------------------------------------------------------
# Integration: main() with mandatory failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_async_returns_1_when_mandatory_endpoint_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """_run_async() must return exit code 1 when a mandatory endpoint fails."""
    monkeypatch.setattr(download_openf1, "asyncio", _fake_asyncio())

    async def fake_discover_session(_args: object) -> SessionRef:
        return SAMPLE_SESSION_REF

    monkeypatch.setattr(download_openf1, "_discover_session", fake_discover_session)

    responses = _happy_path_responses()

    # laps always returns 500 → mandatory failure
    async def _get(path: str, *, params: Any = None, timeout: float = 30.0) -> httpx.Response:
        if path == "/v1/laps":
            return _make_response(500, {})
        return _make_response(200, responses.get(path, []))

    mock_http_client = MagicMock(spec=httpx.AsyncClient)
    mock_http_client.get = AsyncMock(side_effect=_get)

    async def fake_download(session: SessionRef, *, base_url: str = "", http_client: Any = None) -> list[EndpointResult]:
        return await _download_low_frequency(session, http_client=mock_http_client)

    monkeypatch.setattr(download_openf1, "_download_low_frequency", fake_download)

    args = download_openf1.build_parser().parse_args(
        [
            "--fixture-id", "bahrain-2023-race",
            "--year", "2023",
            "--country-name", "Bahrain",
            "--session-name", "Race",
            "--output", str(tmp_path),
        ]
    )

    exit_code = await download_openf1._run_async(args)

    assert exit_code == 1


@pytest.mark.asyncio
async def test_run_async_continues_when_some_drivers_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_discover_session(_args: object) -> SessionRef:
        return SAMPLE_SESSION_REF

    async def fake_download_low_frequency(
        _session: SessionRef,
        *,
        base_url: str = "",
        http_client: Any = None,
    ) -> list[EndpointResult]:
        return [
            EndpointResult("sessions", [{"session_key": 9149}], mandatory=True),
            EndpointResult("drivers", [{"driver_number": 1}], mandatory=True),
            EndpointResult("laps", [{"lap_number": 1}], mandatory=True),
        ]

    async def fake_download_high_frequency(
        _session: SessionRef,
        _drivers: list[int],
        *,
        level: str,
        base_url: str = "",
        sample_rate_hz: int = 1,
        http_client: Any = None,
    ) -> list[DriverEndpointResult]:
        return [
            DriverEndpointResult(
                endpoint="location",
                driver_number=1,
                records_before=[{"date": "2023-03-05T15:00:00Z"}],
                records_after=[{"date": "2023-03-05T15:00:00Z"}],
            ),
            DriverEndpointResult(
                endpoint="car_data",
                driver_number=1,
                records_before=[{"date": "2023-03-05T15:00:00Z"}],
                records_after=[{"date": "2023-03-05T15:00:00Z"}],
            ),
            DriverEndpointResult(
                endpoint="location",
                driver_number=11,
                records_before=[],
                records_after=[],
                error="network error",
            ),
            DriverEndpointResult(
                endpoint="car_data",
                driver_number=11,
                records_before=[],
                records_after=[],
                error="network error",
            ),
        ]

    monkeypatch.setattr(download_openf1, "_discover_session", fake_discover_session)
    monkeypatch.setattr(download_openf1, "_download_low_frequency", fake_download_low_frequency)
    monkeypatch.setattr(download_openf1, "_download_high_frequency", fake_download_high_frequency)

    args = download_openf1.build_parser().parse_args(
        [
            "--fixture-id", "bahrain-2023-race",
            "--year", "2023",
            "--country-name", "Bahrain",
            "--session-name", "Race",
            "--drivers", "1,11",
            "--output", str(tmp_path),
        ]
    )

    exit_code = await download_openf1._run_async(args)

    assert exit_code == 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["high_frequency"]["drivers"]["1"]["location"] == {"before": 1, "after": 1}
    assert "error" in summary["high_frequency"]["drivers"]["11"]["location"]


@pytest.mark.asyncio
async def test_run_async_returns_1_when_all_selected_drivers_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_discover_session(_args: object) -> SessionRef:
        return SAMPLE_SESSION_REF

    async def fake_download_low_frequency(
        _session: SessionRef,
        *,
        base_url: str = "",
        http_client: Any = None,
    ) -> list[EndpointResult]:
        return [
            EndpointResult("sessions", [{"session_key": 9149}], mandatory=True),
            EndpointResult("drivers", [{"driver_number": 1}], mandatory=True),
            EndpointResult("laps", [{"lap_number": 1}], mandatory=True),
        ]

    async def fake_download_high_frequency(
        _session: SessionRef,
        _drivers: list[int],
        *,
        level: str,
        base_url: str = "",
        sample_rate_hz: int = 1,
        http_client: Any = None,
    ) -> list[DriverEndpointResult]:
        return [
            DriverEndpointResult(
                endpoint="location",
                driver_number=1,
                records_before=[],
                records_after=[],
                error="network error",
            ),
            DriverEndpointResult(
                endpoint="car_data",
                driver_number=1,
                records_before=[],
                records_after=[],
                error="network error",
            ),
        ]

    monkeypatch.setattr(download_openf1, "_discover_session", fake_discover_session)
    monkeypatch.setattr(download_openf1, "_download_low_frequency", fake_download_low_frequency)
    monkeypatch.setattr(download_openf1, "_download_high_frequency", fake_download_high_frequency)

    args = download_openf1.build_parser().parse_args(
        [
            "--fixture-id", "bahrain-2023-race",
            "--year", "2023",
            "--country-name", "Bahrain",
            "--session-name", "Race",
            "--drivers", "1",
            "--output", str(tmp_path),
        ]
    )

    exit_code = await download_openf1._run_async(args)

    assert exit_code == 1
    assert not (tmp_path / "summary.json").exists()


# ---------------------------------------------------------------------------
# Metadata checks
# ---------------------------------------------------------------------------

def test_mandatory_endpoints_are_subset_of_low_frequency() -> None:
    assert MANDATORY_ENDPOINTS.issubset(set(LOW_FREQUENCY_ENDPOINTS))


def test_high_frequency_endpoints_not_in_low_frequency() -> None:
    for hf in download_openf1.DEFAULT_HIGH_FREQUENCY_ENDPOINTS:
        assert hf not in LOW_FREQUENCY_ENDPOINTS


# ---------------------------------------------------------------------------
# Helpers (not imported so defined locally)
# ---------------------------------------------------------------------------

def _fake_asyncio():
    """Return a mock asyncio module that makes asyncio.sleep a no-op."""
    import asyncio as real_asyncio

    class _FakeAsyncio:
        sleep = AsyncMock(return_value=None)

        def __getattr__(self, name: str) -> Any:
            return getattr(real_asyncio, name)

    return _FakeAsyncio()
