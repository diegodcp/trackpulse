from __future__ import annotations

import asyncio
import json
from collections.abc import Generator

import pytest
from httpx import ASGITransport, AsyncClient

from trackpulse_api.main import create_app
from trackpulse_api.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _write_fixture(fixtures_dir, name: str, payload: object) -> None:
    (fixtures_dir / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.asyncio
async def test_replay_fixtures_and_state_advance(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures_dir = tmp_path / "openf1"
    fixtures_dir.mkdir()

    _write_fixture(
        fixtures_dir,
        "sessions",
        [
            {
                "session_key": 9149,
                "session_name": "Race",
                "meeting_key": 1210,
                "country_name": "Bahrain",
                "year": 2023,
                "date_start": "2023-03-05T15:00:00+00:00",
            }
        ],
    )
    _write_fixture(
        fixtures_dir,
        "location",
        [
            {
                "date": "2023-03-05T15:00:00.000+00:00",
                "driver_number": 1,
                "session_key": 9149,
                "x": 10.0,
                "y": 20.0,
            },
            {
                "date": "2023-03-05T15:00:00.100+00:00",
                "driver_number": 1,
                "session_key": 9149,
                "x": 14.0,
                "y": 23.0,
            },
            {
                "date": "2023-03-05T15:00:00.200+00:00",
                "driver_number": 11,
                "session_key": 9149,
                "x": 18.0,
                "y": 26.0,
            },
        ],
    )

    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "fixture")
    monkeypatch.setenv("TRACKPULSE_OPENF1_FIXTURE_DATA_DIR", str(fixtures_dir))

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fixtures_response = await client.get("/api/v1/replay/fixtures")
        start_response = await client.post(
            "/api/v1/replay/start",
            json={"fixture_id": "bahrain-2023-race", "speed_multiplier": 10},
        )
        await asyncio.sleep(0.05)
        state_response = await client.get("/api/v1/replay/state")

    assert fixtures_response.status_code == 200
    fixtures_payload = fixtures_response.json()
    assert fixtures_payload == {
        "fixtures": [
            {
                "fixture_id": "bahrain-2023-race",
                "display_name": "Bahrain 2023 Race",
                "source_mode": "fixture",
                "supported_speeds": [1, 5, 10],
            }
        ]
    }

    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    assert state_response.status_code == 200
    state_payload = state_response.json()
    assert state_payload["total_points"] == 3
    assert state_payload["cursor"] >= 1
    assert state_payload["progress_pct"] >= 33.0
    assert state_payload["replay_time"] is not None
    assert state_payload["active_location"] is not None
    assert len(state_payload["timeline_points"]) == 3


@pytest.mark.asyncio
async def test_replay_stop_pauses_and_halts_progress(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures_dir = tmp_path / "openf1"
    fixtures_dir.mkdir()

    _write_fixture(
        fixtures_dir,
        "sessions",
        [
            {
                "session_key": 9149,
                "session_name": "Race",
                "meeting_key": 1210,
                "country_name": "Bahrain",
                "year": 2023,
                "date_start": "2023-03-05T15:00:00+00:00",
            }
        ],
    )
    _write_fixture(
        fixtures_dir,
        "location",
        [
            {
                "date": "2023-03-05T15:00:00.000+00:00",
                "driver_number": 1,
                "session_key": 9149,
                "x": 10.0,
                "y": 20.0,
            },
            {
                "date": "2023-03-05T15:00:00.200+00:00",
                "driver_number": 1,
                "session_key": 9149,
                "x": 14.0,
                "y": 23.0,
            },
            {
                "date": "2023-03-05T15:00:00.400+00:00",
                "driver_number": 11,
                "session_key": 9149,
                "x": 18.0,
                "y": 26.0,
            },
        ],
    )

    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "fixture")
    monkeypatch.setenv("TRACKPULSE_OPENF1_FIXTURE_DATA_DIR", str(fixtures_dir))

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/replay/start",
            json={"fixture_id": "bahrain-2023-race", "speed_multiplier": 1},
        )
        await asyncio.sleep(0.05)

        stop_response = await client.post("/api/v1/replay/stop")
        cursor_after_stop = stop_response.json()["cursor"]

        await asyncio.sleep(0.3)
        state_response = await client.get("/api/v1/replay/state")

    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "paused"

    assert state_response.status_code == 200
    state_payload = state_response.json()
    assert state_payload["status"] == "paused"
    assert state_payload["cursor"] == cursor_after_stop
