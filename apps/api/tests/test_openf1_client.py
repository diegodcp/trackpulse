from __future__ import annotations

import logging

import httpx
import pytest

from trackpulse_api.openf1 import OpenF1HistoricalClient, OpenF1RequestError


@pytest.mark.asyncio
async def test_openf1_client_builds_correct_urls() -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenF1HistoricalClient(
            base_url="https://api.openf1.org",
            http_client=http_client,
        )
        await client.get_weather(session_key=9149)

    assert len(captured) == 1
    assert captured[0].url.path == "/v1/weather"
    assert captured[0].url.params["session_key"] == "9149"


@pytest.mark.asyncio
async def test_openf1_client_parses_fixture_payloads(tmp_path) -> None:
    fixtures_dir = tmp_path / "openf1"
    fixtures_dir.mkdir()
    (fixtures_dir / "weather.json").write_text(
        """
        [
          {
            "date": "2023-03-05T15:00:00+00:00",
            "session_key": 9149,
            "track_temperature": 41.2,
            "wind_speed": 2.7,
            "rainfall": false
          }
        ]
        """,
        encoding="utf-8",
    )

    client = OpenF1HistoricalClient(
        mode="fixture",
        fixture_data_dir=fixtures_dir,
    )

    weather = await client.get_weather(session_key=9149)

    assert len(weather) == 1
    assert weather[0].session_key == 9149
    assert weather[0].track_temperature == pytest.approx(41.2)
    assert weather[0].rainfall is False


@pytest.mark.asyncio
async def test_openf1_client_handles_timeout_with_retry() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.TimeoutException("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenF1HistoricalClient(
            http_client=http_client,
            max_retries=2,
            retry_backoff_seconds=0.0,
        )

        with pytest.raises(OpenF1RequestError, match="failed after 3 attempts"):
            await client.get_weather(session_key=9149)

    assert attempts == 3


@pytest.mark.asyncio
async def test_openf1_client_redacts_authorization_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenF1HistoricalClient(
            bearer_token="super-secret-token",
            http_client=http_client,
        )

        with caplog.at_level(logging.DEBUG):
            await client.get_weather(session_key=9149)

    assert "super-secret-token" not in caplog.text
    assert "Bearer [REDACTED]" in caplog.text
