from __future__ import annotations

import logging
from urllib.parse import parse_qs

import httpx
import pytest

from trackpulse_api.openf1 import (
    OpenF1HistoricalClient,
    SessionDiscoveryQuery,
    SessionNotFoundError,
)


@pytest.mark.asyncio
async def test_discover_session_returns_single_result() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/sessions"
        assert request.url.params["year"] == "2023"
        assert request.url.params["country_name"] == "Bahrain"
        assert request.url.params["session_name"] == "Race"
        return httpx.Response(
            200,
            json=[
                {
                    "session_key": 1001,
                    "session_name": "Race",
                    "date_start": "2023-03-05T15:00:00+00:00",
                    "meeting_key": 55,
                    "country_name": "Bahrain",
                }
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenF1HistoricalClient(http_client=http_client)
        session = await client.discover_session(
            SessionDiscoveryQuery(year=2023, country_name="Bahrain", session_name="Race")
        )

    assert session.session_key == 1001
    assert session.session_name == "Race"
    assert session.country_name == "Bahrain"


@pytest.mark.asyncio
async def test_discover_session_raises_not_found_for_empty_result() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/sessions"
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenF1HistoricalClient(http_client=http_client)

        with pytest.raises(SessionNotFoundError):
            await client.discover_session(
                SessionDiscoveryQuery(year=2023, country_name="Bahrain", session_name="Race")
            )


@pytest.mark.asyncio
async def test_discover_session_selects_exact_match_then_earliest_date(caplog: pytest.LogCaptureFixture) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "session_key": 2003,
                    "session_name": "Practice 1",
                    "date_start": "2023-03-03T11:00:00+00:00",
                },
                {
                    "session_key": 2002,
                    "session_name": "Race",
                    "date_start": "2023-03-05T14:00:00+00:00",
                },
                {
                    "session_key": 2001,
                    "session_name": "Race",
                    "date_start": "2023-03-05T13:00:00+00:00",
                },
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenF1HistoricalClient(http_client=http_client)

        with caplog.at_level(logging.WARNING):
            selected = await client.discover_session(
                SessionDiscoveryQuery(year=2023, country_name="Bahrain", session_name="Race")
            )

    assert selected.session_key == 2001
    assert "Multiple OpenF1 sessions matched query" in caplog.text


@pytest.mark.asyncio
async def test_discover_session_encodes_query_parameters_safely() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raw_query = request.url.query.decode("ascii")
        parsed_query = parse_qs(raw_query)

        assert " " not in raw_query
        assert "%26" in raw_query
        assert "%2F" in raw_query
        assert parsed_query == {
            "year": ["2023"],
            "country_name": ["Saudi Arabia"],
            "session_name": ["Race & Sprint/Final"],
        }

        return httpx.Response(
            200,
            json=[
                {
                    "session_key": 3010,
                    "session_name": "Race & Sprint/Final",
                    "date_start": "2023-03-19T17:00:00+00:00",
                }
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenF1HistoricalClient(http_client=http_client)
        selected = await client.discover_session(
            SessionDiscoveryQuery(
                year=2023,
                country_name="Saudi Arabia",
                session_name="Race & Sprint/Final",
            )
        )

    assert selected.session_key == 3010
