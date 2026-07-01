from __future__ import annotations

import pytest

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
    assert len(snapshot.segment_states) == 16

    first_segment = snapshot.segment_states[0]
    assert first_segment["segment_id"] == "bh-s01"
    assert first_segment["measured"]["truth_label"] == "measured"
    assert first_segment["derived"]["truth_label"] == "derived"
    assert first_segment["derived"]["wind_class"] in {
        "headwind",
        "tailwind",
        "crosswind_left",
        "crosswind_right",
        "unknown",
    }


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
    assert len(snapshot.segment_states) == 16
    assert snapshot.segment_states[0]["derived"]["wind_class"] == "unknown"
    assert snapshot.connection_status == "connected"
    assert snapshot.replay_status == "idle"


def test_reducer_wind_projection_changes_when_wind_direction_changes() -> None:
    reducer = TrackStateReducer()

    snapshot_headwind = reducer.apply_event(
        {
            "fixture_id": "bahrain-2023-race",
            "event_type": "weather",
            "session_key": 9149,
            "occurred_at": "2023-03-05T15:00:00.000Z",
            "payload": {
                "wind_direction": 162,
                "wind_speed": 10.0,
            },
        }
    )
    snapshot_tailwind = reducer.apply_event(
        {
            "fixture_id": "bahrain-2023-race",
            "event_type": "weather",
            "session_key": 9149,
            "occurred_at": "2023-03-05T15:00:02.000Z",
            "payload": {
                "wind_direction": 342,
                "wind_speed": 10.0,
            },
        }
    )

    segment_headwind = next(item for item in snapshot_headwind.segment_states if item["segment_id"] == "bh-s01")
    segment_tailwind = next(item for item in snapshot_tailwind.segment_states if item["segment_id"] == "bh-s01")

    assert segment_headwind["derived"]["wind_class"] == "headwind"
    assert segment_tailwind["derived"]["wind_class"] == "tailwind"
    assert segment_headwind["derived"]["wind_relative_angle_deg"] == pytest.approx(0.0)
    assert segment_tailwind["derived"]["wind_relative_angle_deg"] == pytest.approx(-180.0)


def test_reducer_traffic_scores_are_zero_when_no_cars_present() -> None:
    reducer = TrackStateReducer()

    snapshot = reducer.snapshot()

    assert len(snapshot.segment_states) == 16
    assert all(segment["derived"]["traffic_score"] == pytest.approx(0.0) for segment in snapshot.segment_states)
    assert all(segment["derived"]["traffic_truth_label"] == "derived" for segment in snapshot.segment_states)


def test_reducer_traffic_scores_include_single_car_own_and_adjacent_segments() -> None:
    reducer = TrackStateReducer()

    snapshot = reducer.apply_event(
        {
            "event_type": "location",
            "driver_number": 1,
            "occurred_at": "2023-03-05T15:00:00.000Z",
            "payload": {
                "x": 10.0,
                "y": 20.0,
                "segment_id": "bh-s03",
            },
        }
    )

    scores = {item["segment_id"]: item["derived"]["traffic_score"] for item in snapshot.segment_states}

    assert scores["bh-s03"] == pytest.approx(20.0)
    assert scores["bh-s02"] == pytest.approx(10.0)
    assert scores["bh-s04"] == pytest.approx(10.0)
    assert scores["bh-s01"] == pytest.approx(0.0)


def test_reducer_traffic_scores_increase_for_clustered_cars() -> None:
    reducer = TrackStateReducer()

    reducer.apply_event(
        {
            "event_type": "location",
            "driver_number": 1,
            "occurred_at": "2023-03-05T15:00:00.000Z",
            "payload": {
                "x": 10.0,
                "y": 20.0,
                "segment_id": "bh-s08",
            },
        }
    )
    snapshot = reducer.apply_event(
        {
            "event_type": "location",
            "driver_number": 11,
            "occurred_at": "2023-03-05T15:00:00.100Z",
            "payload": {
                "x": 12.0,
                "y": 22.0,
                "segment_id": "bh-s08",
            },
        }
    )

    scores = {item["segment_id"]: item["derived"]["traffic_score"] for item in snapshot.segment_states}

    assert scores["bh-s08"] == pytest.approx(40.0)
    assert scores["bh-s07"] == pytest.approx(20.0)
    assert scores["bh-s09"] == pytest.approx(20.0)
