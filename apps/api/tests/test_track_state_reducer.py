from __future__ import annotations

from trackpulse_api.state import TrackStateReducer


def test_reducer_updates_weather_state() -> None:
    reducer = TrackStateReducer()

    snapshot = reducer.apply_event(
        {
            "fixture_id": "bahrain-2023-race",
            "event_type": "weather",
            "session_key": 9149,
            "occurred_at": "2023-03-05T15:00:00.000Z",
            "payload": {
                "track_temperature": 42.3,
                "air_temperature": 31.0,
                "humidity": 25.0,
                "pressure": 1012.1,
                "rainfall": False,
                "wind_direction": 95,
                "wind_speed": 3.6,
            },
        }
    )

    assert snapshot.fixture_id == "bahrain-2023-race"
    assert snapshot.session_key == 9149
    assert snapshot.replay_time == "2023-03-05T15:00:00.000Z"
    assert snapshot.weather.available is True
    assert snapshot.weather.track_temperature_c == 42.3
    assert snapshot.weather.wind_speed_ms == 3.6
    assert snapshot.weather.truth_label == "measured"


def test_reducer_accepts_updated_event_type_variant() -> None:
    reducer = TrackStateReducer()

    snapshot = reducer.apply_event(
        {
            "fixture_id": "bahrain-2023-race",
            "event_type": "weather.updated",
            "session_key": 9149,
            "occurred_at": "2023-03-05T15:00:00.000Z",
            "payload": {
                "track_temperature": 40.0,
                "air_temperature": 30.5,
            },
        }
    )

    assert snapshot.weather.available is True
    assert snapshot.weather.track_temperature_c == 40.0


def test_reducer_keeps_latest_location_per_driver() -> None:
    reducer = TrackStateReducer(fixture_id="bahrain-2023-race")

    reducer.apply_event(
        {
            "event_type": "location",
            "driver_number": 1,
            "session_key": 9149,
            "occurred_at": "2023-03-05T15:00:00.100Z",
            "payload": {"x": 10.0, "y": 20.0, "z": 1.0},
        }
    )
    snapshot = reducer.apply_event(
        {
            "event_type": "location",
            "driver_number": 1,
            "session_key": 9149,
            "occurred_at": "2023-03-05T15:00:00.300Z",
            "payload": {"x": 14.0, "y": 23.0, "z": 1.1},
        }
    )

    assert snapshot.replay_time == "2023-03-05T15:00:00.300Z"
    assert len(snapshot.car_markers) == 1
    assert snapshot.car_markers[0].driver_number == 1
    assert snapshot.car_markers[0].x == 14.0
    assert snapshot.car_markers[0].y == 23.0
    assert snapshot.car_markers[0].location_label == "approximate"


def test_reducer_builds_snapshot_without_weather() -> None:
    reducer = TrackStateReducer()

    snapshot = reducer.reduce_events(
        [
            {
                "fixture_id": "bahrain-2023-race",
                "event_type": "location",
                "session_key": 9149,
                "driver_number": 1,
                "occurred_at": "2023-03-05T15:00:00.000Z",
                "payload": {"x": 10.0, "y": 20.0},
            },
            {
                "fixture_id": "bahrain-2023-race",
                "event_type": "location",
                "session_key": 9149,
                "driver_number": 11,
                "occurred_at": "2023-03-05T15:00:00.200Z",
                "payload": {"x": 18.0, "y": 26.0},
            },
        ]
    )

    assert snapshot.fixture_id == "bahrain-2023-race"
    assert snapshot.replay_time == "2023-03-05T15:00:00.200Z"
    assert snapshot.weather.available is False
    assert snapshot.weather.track_temperature_c is None
    assert [marker.driver_number for marker in snapshot.car_markers] == [1, 11]
    assert snapshot.segment_states == [{"status": "not_implemented", "truth_label": "derived"}]
    assert snapshot.connection_status == "connected"
    assert snapshot.replay_status == "idle"
