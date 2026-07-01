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
async def test_replay_api_endpoints_expose_fixture_manifest_status_and_track_state(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_root = tmp_path / "bahrain-2023-race"
    fixtures_dir = fixture_root / "golden"
    fixtures_dir.mkdir(parents=True)

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
                "date": "2023-03-05T15:00:02.000+00:00",
                "driver_number": 1,
                "session_key": 9149,
                "x": 14.0,
                "y": 23.0,
            },
            {
                "date": "2023-03-05T15:00:04.000+00:00",
                "driver_number": 11,
                "session_key": 9149,
                "x": 18.0,
                "y": 26.0,
            },
        ],
    )
    _write_fixture(
        fixtures_dir,
        "weather",
        [
            {
                "date": "2023-03-05T15:00:00+00:00",
                "session_key": 9149,
                "track_temperature": 43.2,
                "wind_speed": 2.7,
                "wind_direction": 192,
                "rainfall": False,
            }
        ],
    )
    (fixture_root / "manifest.template.json").write_text(
        json.dumps(
            {
                "fixture_id": "bahrain-2023-race",
                "fixture_version": 1,
                "source": "openf1-rest-historical",
                "seed_query": {
                    "year": 2023,
                    "country_name": "Bahrain",
                    "session_name": "Race",
                },
                "drivers": [1, 11, 14, 16, 44],
                "endpoints": ["sessions", "weather", "location"],
                "sampling": {"modes": {"golden": {"location_hz_target": 1.0}}},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "fixture")
    monkeypatch.setenv("TRACKPULSE_OPENF1_FIXTURE_DATA_DIR", str(fixtures_dir))

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fixtures_response = await client.get("/api/v1/fixtures")
        manifest_response = await client.get("/api/v1/fixtures/bahrain-2023-race/manifest")
        start_response = await client.post(
            "/api/v1/replay/bahrain-2023-race/start",
            json={"speed_multiplier": 20},
        )
        await asyncio.sleep(0.03)
        replay_status_response = await client.get("/api/v1/events/replay-status")
        track_state_response = await client.get("/api/v1/track-state/latest")
        pause_response = await client.post("/api/v1/replay/bahrain-2023-race/pause")

    assert fixtures_response.status_code == 200
    fixtures_payload = fixtures_response.json()
    assert fixtures_payload == {
        "fixtures": [
            {
                "fixture_id": "bahrain-2023-race",
                "display_name": "Bahrain 2023 Race",
                "source_mode": "fixture",
                "supported_speeds": [1, 5, 20, 100],
            }
        ]
    }

    assert manifest_response.status_code == 200
    manifest_payload = manifest_response.json()
    assert manifest_payload["fixture_id"] == "bahrain-2023-race"
    assert manifest_payload["manifest"]["fixture_id"] == "bahrain-2023-race"

    assert start_response.status_code == 200
    assert start_response.json() == {
        "fixture_id": "bahrain-2023-race",
        "status": "running",
        "speed_multiplier": 20,
        "cursor": 0,
        "total_points": 3,
        "progress_pct": 0.0,
        "replay_time": None,
        "message": "Replay started",
    }

    assert replay_status_response.status_code == 200
    replay_status_payload = replay_status_response.json()
    assert replay_status_payload["fixture_id"] == "bahrain-2023-race"
    assert replay_status_payload["status"] in {"running", "completed"}
    assert replay_status_payload["total_points"] == 3

    assert track_state_response.status_code == 200
    track_state_payload = track_state_response.json()
    snapshot = track_state_payload["snapshot"]
    assert snapshot["fixture_id"] == "bahrain-2023-race"
    assert isinstance(snapshot["weather"], dict)
    assert snapshot["weather"]["truth_label"] == "measured"
    assert isinstance(snapshot["car_markers"], list)
    assert snapshot["replay_status"] in {"running", "completed"}

    assert pause_response.status_code == 200
    assert pause_response.json()["status"] in {"paused", "completed"}


@pytest.mark.asyncio
async def test_replay_api_invalid_fixture_returns_404_with_clear_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_root = tmp_path / "bahrain-2023-race"
    fixtures_dir = fixture_root / "golden"
    fixtures_dir.mkdir(parents=True)

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
    _write_fixture(fixtures_dir, "location", [])

    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "fixture")
    monkeypatch.setenv("TRACKPULSE_OPENF1_FIXTURE_DATA_DIR", str(fixtures_dir))

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start_response = await client.post(
            "/api/v1/replay/not-a-real-fixture/start",
            json={"speed_multiplier": 1},
        )
        manifest_response = await client.get("/api/v1/fixtures/not-a-real-fixture/manifest")

    assert start_response.status_code == 404
    assert start_response.json() == {"detail": "Fixture 'not-a-real-fixture' was not found"}

    assert manifest_response.status_code == 404
    assert manifest_response.json() == {"detail": "Fixture 'not-a-real-fixture' was not found"}
