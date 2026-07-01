from __future__ import annotations

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
async def test_openf1_proxy_endpoints_return_fixture_envelopes(
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
        "weather",
        [
            {
                "date": "2023-03-05T15:00:00+00:00",
                "session_key": 9149,
                "track_temperature": 41.2,
                "wind_speed": 2.1,
                "wind_direction": 180,
                "rainfall": False,
            },
            {
                "date": "2023-03-05T15:01:00+00:00",
                "session_key": 9149,
                "track_temperature": 43.2,
                "air_temperature": 29.4,
                "wind_speed": 2.7,
                "wind_direction": 192,
                "rainfall": False,
            },
        ],
    )
    _write_fixture(
        fixtures_dir,
        "location",
        [
            {
                "date": "2023-03-05T15:00:00+00:00",
                "driver_number": 1,
                "session_key": 9149,
                "meeting_key": 1210,
                "x": 10.0,
                "y": 20.0,
                "z": 0.0,
            },
            {
                "date": "2023-03-05T15:00:01+00:00",
                "driver_number": 11,
                "session_key": 9149,
                "meeting_key": 1210,
                "x": 11.0,
                "y": 21.0,
                "z": 0.0,
            },
        ],
    )

    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "fixture")
    monkeypatch.setenv("TRACKPULSE_OPENF1_FIXTURE_DATA_DIR", str(fixtures_dir))
    monkeypatch.setenv("TRACKPULSE_OPENF1_SEED_YEAR", "2023")
    monkeypatch.setenv("TRACKPULSE_OPENF1_SEED_COUNTRY_NAME", "Bahrain")
    monkeypatch.setenv("TRACKPULSE_OPENF1_SEED_SESSION_NAME", "Race")

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        session_response = await client.get("/api/v1/sessions/latest")
        weather_response = await client.get("/api/v1/openf1/weather/latest")
        location_response = await client.get("/api/v1/openf1/location/sample")
        track_state_response = await client.get("/api/v1/track-state/latest")

    assert session_response.status_code == 200
    assert session_response.json()["data"]["session_key"] == 9149
    assert session_response.json()["meta"]["request_id"]

    assert weather_response.status_code == 200
    assert weather_response.json()["data"]["track_temperature"] == pytest.approx(43.2)
    assert weather_response.json()["meta"]["request_id"]

    assert location_response.status_code == 200
    assert len(location_response.json()["data"]) == 2
    assert location_response.json()["data"][0]["driver_number"] == 1
    assert location_response.json()["meta"]["request_id"]

    assert track_state_response.status_code == 200
    track_state_payload = track_state_response.json()
    assert track_state_payload["meta"]["request_id"]

    segments = track_state_payload["data"]
    assert len(segments) == 12

    first_segment = segments[0]
    assert first_segment["segmentId"] == "s01"
    assert first_segment["sessionKey"] == "fixture"
    assert first_segment["updatedAt"] == "2023-03-05T15:01:00+00:00"

    # TP-LAYER-01 truth buckets: measured from weather, derived placeholders, inferred confidence placeholder.
    assert first_segment["measured"] == {
        "trackTemperatureC": pytest.approx(43.2),
        "airTemperatureC": pytest.approx(29.4),
        "windSpeedMs": pytest.approx(2.7),
        "windDirectionDeg": 192,
        "rainfall": False,
    }
    assert 0.0 <= first_segment["derived"]["trafficScore"] <= 100.0
    assert 0.0 <= first_segment["derived"]["windStrengthScore"] <= 100.0
    assert first_segment["derived"]["windClass"] in {
        "headwind",
        "tailwind",
        "crosswind_left",
        "crosswind_right",
        "unknown",
    }
    assert first_segment["inferred"]["confidence"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_openf1_proxy_returns_controlled_error_for_invalid_fixture(
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
    _write_fixture(fixtures_dir, "weather", {"track_temperature": 43.2})

    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "fixture")
    monkeypatch.setenv("TRACKPULSE_OPENF1_FIXTURE_DATA_DIR", str(fixtures_dir))

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/openf1/weather/latest")

    payload = response.json()
    assert response.status_code == 502
    assert payload == {
        "error": {
            "code": "openf1_payload_invalid",
            "message": "The backend received an invalid OpenF1 payload.",
        },
        "meta": {"request_id": payload["meta"]["request_id"]},
    }


@pytest.mark.asyncio
async def test_openf1_proxy_never_exposes_bearer_token_to_frontend(
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
        "weather",
        [
            {
                "date": "2023-03-05T15:01:00+00:00",
                "session_key": 9149,
                "track_temperature": 43.2,
                "air_temperature": 29.4,
                "wind_speed": 2.7,
                "wind_direction": 192,
                "rainfall": False,
            }
        ],
    )

    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "fixture")
    monkeypatch.setenv("TRACKPULSE_OPENF1_FIXTURE_DATA_DIR", str(fixtures_dir))
    monkeypatch.setenv("TRACKPULSE_OPENF1_BEARER_TOKEN", "super-secret-token")

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/openf1/weather/latest")

    assert response.status_code == 200
    assert "super-secret-token" not in response.text
    assert all("super-secret-token" not in value for value in response.headers.values())


@pytest.mark.asyncio
async def test_openf1_proxy_uses_default_committed_fixture_data() -> None:
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/openf1/weather/latest")

    payload = response.json()
    assert response.status_code == 200
    assert payload["data"]["session_key"] == 9149
    assert payload["data"]["track_temperature"] == pytest.approx(43.2)
    assert payload["data"]["air_temperature"] == pytest.approx(29.4)
    assert payload["data"]["rainfall"] is False