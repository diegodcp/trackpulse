from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from trackpulse_api.main import create_app
from trackpulse_api.openf1 import OpenF1Location, OpenF1Session, OpenF1Weather
from trackpulse_api.routes import replay as replay_routes
from trackpulse_api.routes.replay import _controller, _track_state_sse_events
from trackpulse_api.settings import AppSettings
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
                "x": 10.2,
                "y": 20.2,
            },
            {
                "date": "2023-03-05T15:00:04.000+00:00",
                "driver_number": 11,
                "session_key": 9149,
                "x": 10.4,
                "y": 20.4,
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
            },
            {
                "date": "2023-03-05T15:00:03+00:00",
                "session_key": 9149,
                "track_temperature": 42.8,
                "wind_speed": 3.1,
                "wind_direction": 342,
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
        await asyncio.sleep(0.14)
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
    assert snapshot["weather"]["available"] is True
    assert snapshot["weather"]["truth_label"] == "measured"
    assert isinstance(snapshot["car_markers"], list)
    assert isinstance(snapshot["segment_states"], list)
    assert isinstance(snapshot["live_insights"], list)
    assert len(snapshot["segment_states"]) == 16
    assert snapshot["segment_states"][0]["measured"]["truth_label"] == "measured"
    assert snapshot["segment_states"][0]["derived"]["truth_label"] == "derived"
    assert "traffic_score" in snapshot["segment_states"][0]["derived"]
    assert snapshot["segment_states"][0]["derived"]["traffic_truth_label"] == "derived"
    assert snapshot["replay_status"] in {"running", "completed"}
    assert all(item.get("truth_label") == "inferred" for item in snapshot["live_insights"])

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


@pytest.mark.asyncio
async def test_track_state_sse_stream_emits_track_state_and_heartbeat_events(
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

    class _ConnectedRequest:
        def __init__(self, target_app) -> None:
            self.app = target_app

        async def is_disconnected(self) -> bool:
            return False

    request = _ConnectedRequest(app)
    controller = _controller(request)

    events: list[tuple[str, dict[str, object]]] = []
    async for event_raw in _track_state_sse_events(request, controller, max_events=2):
        lines = [line for line in event_raw.strip().split("\n") if line]
        event_name = lines[0].removeprefix("event: ")
        payload = json.loads(lines[1].removeprefix("data: "))
        events.append((event_name, payload))

    assert events[0][0] == "track_state"
    assert events[0][1]["event_type"] == "track_state"
    assert isinstance(events[0][1]["snapshot"], dict)
    assert events[0][1]["snapshot"]["weather"]["available"] is False

    assert events[1][0] == "heartbeat"
    assert events[1][1] == {
        "fixture_id": "bahrain-2023-race",
        "replay_status": "idle",
        "event_type": "heartbeat",
    }


@pytest.mark.asyncio
async def test_track_state_latest_historical_uses_batched_location_fetch_and_cached_session_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubClient:
        def __init__(self) -> None:
            self.discover_session_calls = 0
            self.get_weather_calls = 0
            self.get_location_batch_calls = 0
            self.last_location_batch_limit: int | None = None
            self.last_location_batch_drivers: tuple[int, ...] = ()

        async def discover_session(self, query) -> OpenF1Session:  # noqa: ANN001
            self.discover_session_calls += 1
            return OpenF1Session(
                session_key=9150,
                session_name=query.session_name,
                country_name=query.country_name,
                year=query.year,
            )

        async def get_weather(self, *, session_key: int | None = None, limit: int | None = None) -> list[OpenF1Weather]:
            self.get_weather_calls += 1
            return [
                OpenF1Weather(
                    date=datetime.fromisoformat("2023-03-05T15:02:00+00:00"),
                    session_key=session_key,
                    track_temperature=44.1,
                    air_temperature=30.1,
                    wind_speed=3.2,
                    wind_direction=196,
                    rainfall=False,
                )
            ]

        async def get_location_batch(
            self,
            *,
            session_key: int,
            driver_numbers: tuple[int, ...] | list[int],
            limit: int | None = None,
        ) -> dict[int, list[OpenF1Location]]:
            self.get_location_batch_calls += 1
            self.last_location_batch_limit = limit
            self.last_location_batch_drivers = tuple(driver_numbers)
            return {
                1: [
                    OpenF1Location(
                        date=datetime(2023, 3, 5, 15, 2, 0, tzinfo=timezone.utc),
                        driver_number=1,
                        session_key=session_key,
                        x=100.0,
                        y=200.0,
                    ),
                    OpenF1Location(
                        date=datetime(2023, 3, 5, 15, 2, 1, tzinfo=timezone.utc),
                        driver_number=1,
                        session_key=session_key,
                        x=104.0,
                        y=204.0,
                    ),
                ],
                11: [
                    OpenF1Location(
                        date=datetime(2023, 3, 5, 15, 2, 2, tzinfo=timezone.utc),
                        driver_number=11,
                        session_key=session_key,
                        x=108.0,
                        y=208.0,
                    )
                ],
            }

    stub_client = StubClient()
    monkeypatch.setattr(replay_routes, "_build_openf1_client", lambda request: stub_client)

    app = create_app(
        AppSettings(
            openf1_mode="historical",
            openf1_seed_year=2023,
            openf1_seed_country_name="Bahrain",
            openf1_seed_session_name="Race",
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first_response = await client.get("/api/v1/track-state/latest")
        second_response = await client.get("/api/v1/track-state/latest")

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_snapshot = first_response.json()["snapshot"]
    assert first_snapshot["session_key"] == 9150
    assert first_snapshot["weather"]["available"] is True
    assert first_snapshot["weather"]["truth_label"] == "measured"
    assert len(first_snapshot["car_markers"]) == 2
    assert len(first_snapshot["segment_states"]) == 16

    assert stub_client.discover_session_calls == 1
    assert stub_client.get_weather_calls == 2
    assert stub_client.get_location_batch_calls == 2
    assert stub_client.last_location_batch_limit == 5
    assert stub_client.last_location_batch_drivers == (1, 11, 14, 16, 44)


@pytest.mark.asyncio
async def test_track_state_latest_historical_keeps_replay_snapshot_when_running(
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
                "x": 10.2,
                "y": 20.2,
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

    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "historical")
    monkeypatch.setenv("TRACKPULSE_OPENF1_FIXTURE_DATA_DIR", str(fixtures_dir))

    class GuardClient:
        async def discover_session(self, query) -> OpenF1Session:  # noqa: ANN001
            raise AssertionError("historical fallback should not run when replay is active")

        async def get_weather(self, *, session_key: int | None = None, limit: int | None = None) -> list[OpenF1Weather]:
            raise AssertionError("historical fallback should not run when replay is active")

        async def get_location_batch(
            self,
            *,
            session_key: int,
            driver_numbers: tuple[int, ...] | list[int],
            limit: int | None = None,
        ) -> dict[int, list[OpenF1Location]]:
            raise AssertionError("historical fallback should not run when replay is active")

    monkeypatch.setattr(replay_routes, "_build_openf1_client", lambda request: GuardClient())

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start_response = await client.post(
            "/api/v1/replay/bahrain-2023-race/start",
            json={"speed_multiplier": 20},
        )
        await asyncio.sleep(0.05)
        track_state_response = await client.get("/api/v1/track-state/latest")

    assert start_response.status_code == 200
    assert track_state_response.status_code == 200
    payload = track_state_response.json()["snapshot"]
    assert payload["fixture_id"] == "bahrain-2023-race"
    assert payload["replay_status"] in {"running", "completed"}
