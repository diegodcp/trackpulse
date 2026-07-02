"""Tests that all ORM models are importable and metadata is consistent."""

from sqlalchemy import inspect

from trackpulse_api.db.base import Base
from trackpulse_api.db.models import (
    CarPosition,
    CarTelemetry,
    CarTimeline,
    CircuitGeometry,
    ConditionSnapshot,
    Driver,
    Insight,
    Interval,
    Lap,
    Meeting,
    PitStop,
    Position,
    RaceControlEvent,
    Session,
    Stint,
    WeatherSample,
)


EXPECTED_TABLES = {
    "meetings",
    "sessions",
    "drivers",
    "car_positions",
    "car_telemetry",
    "weather_samples",
    "laps",
    "stints",
    "race_control_events",
    "intervals",
    "positions",
    "pit_stops",
    "circuit_geometry",
    "condition_snapshots",
    "car_timeline",
    "insights",
}


def test_all_tables_registered_in_metadata():
    """All 16 tables from the DB model are registered in Base.metadata."""
    registered = set(Base.metadata.tables.keys())
    assert EXPECTED_TABLES.issubset(registered), f"Missing: {EXPECTED_TABLES - registered}"


def test_meetings_columns():
    mapper = inspect(Meeting)
    cols = {c.key for c in mapper.column_attrs}
    assert "meeting_key" in cols
    assert "year" in cols
    assert "circuit_short_name" in cols


def test_sessions_columns():
    mapper = inspect(Session)
    cols = {c.key for c in mapper.column_attrs}
    assert "session_key" in cols
    assert "session_type" in cols
    assert "meeting_id" in cols


def test_drivers_columns():
    mapper = inspect(Driver)
    cols = {c.key for c in mapper.column_attrs}
    assert "driver_number" in cols
    assert "team_colour" in cols
    assert "name_acronym" in cols


def test_car_positions_columns():
    mapper = inspect(CarPosition)
    cols = {c.key for c in mapper.column_attrs}
    assert "x" in cols
    assert "y" in cols
    assert "z" in cols


def test_car_telemetry_columns():
    mapper = inspect(CarTelemetry)
    cols = {c.key for c in mapper.column_attrs}
    assert "speed" in cols
    assert "rpm" in cols
    assert "drs" in cols


def test_weather_samples_columns():
    mapper = inspect(WeatherSample)
    cols = {c.key for c in mapper.column_attrs}
    assert "wind_speed" in cols
    assert "rainfall" in cols


def test_laps_columns():
    mapper = inspect(Lap)
    cols = {c.key for c in mapper.column_attrs}
    assert "lap_duration" in cols
    assert "segments_sector_1" in cols


def test_stints_columns():
    mapper = inspect(Stint)
    cols = {c.key for c in mapper.column_attrs}
    assert "compound" in cols
    assert "tyre_age_at_start" in cols


def test_race_control_events_columns():
    mapper = inspect(RaceControlEvent)
    cols = {c.key for c in mapper.column_attrs}
    assert "category" in cols
    assert "flag" in cols
    assert "message" in cols


def test_intervals_columns():
    mapper = inspect(Interval)
    cols = {c.key for c in mapper.column_attrs}
    assert "gap_to_leader" in cols
    assert "interval_ahead" in cols


def test_positions_columns():
    mapper = inspect(Position)
    cols = {c.key for c in mapper.column_attrs}
    assert "position" in cols


def test_pit_stops_columns():
    mapper = inspect(PitStop)
    cols = {c.key for c in mapper.column_attrs}
    assert "pit_duration" in cols
    assert "stop_duration" in cols


def test_circuit_geometry_columns():
    mapper = inspect(CircuitGeometry)
    cols = {c.key for c in mapper.column_attrs}
    assert "centerline" in cols
    assert "segments" in cols
    assert "bounds" in cols
    assert "total_length" in cols


def test_condition_snapshots_columns():
    mapper = inspect(ConditionSnapshot)
    cols = {c.key for c in mapper.column_attrs}
    assert "weather" in cols
    assert "segment_conditions" in cols
    assert "rain_zones" in cols


def test_car_timeline_columns():
    mapper = inspect(CarTimeline)
    cols = {c.key for c in mapper.column_attrs}
    assert "x" in cols
    assert "compound" in cols
    assert "drs_active" in cols
    assert "segment_id" in cols


def test_insights_columns():
    mapper = inspect(Insight)
    cols = {c.key for c in mapper.column_attrs}
    assert "severity" in cols
    assert "data_label" in cols
    assert "category" in cols
    assert "evidence" in cols
    assert "confidence" in cols
