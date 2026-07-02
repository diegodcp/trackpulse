"""Initial schema — all tables from TrackPulse database model"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, ENUM as PgENUM

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_enum(name: str, values: list[str]) -> PgENUM:
    """Create a PostgreSQL ENUM type idempotently, return a column type reference."""
    op.execute(sa.text(f"DROP TYPE IF EXISTS {name}"))
    values_sql = ", ".join(f"'{v}'" for v in values)
    op.execute(sa.text(f"CREATE TYPE {name} AS ENUM ({values_sql})"))
    # Return PgENUM with create_type=False so op.create_table won't re-create it
    return PgENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    # --- ENUMs ---
    session_type = _create_enum(
        "session_type", ["Practice", "Qualifying", "Sprint", "Race"]
    )
    tyre_compound = _create_enum(
        "tyre_compound", ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]
    )
    flag_type = _create_enum(
        "flag_type", ["GREEN", "YELLOW", "DOUBLE_YELLOW", "RED", "CHEQUERED",
                      "BLACK_AND_WHITE", "BLUE", "VSC"]
    )
    race_control_category = _create_enum(
        "race_control_category", ["Flag", "SafetyCar", "Drs", "CarEvent", "SessionStatus", "Other"]
    )
    _create_enum("condition_level", ["very_low", "low", "moderate", "high", "very_high"])
    _create_enum("evolution_trend", ["improving", "stable", "worsening", "insufficient_data"])
    insight_severity = _create_enum(
        "insight_severity", ["info", "warning", "critical"]
    )
    data_label = _create_enum(
        "data_label", ["measured", "derived", "inferred"]
    )

    # --- meetings ---
    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("meeting_key", sa.Integer, unique=True, nullable=False),
        sa.Column("meeting_name", sa.String(100), nullable=False),
        sa.Column("country_name", sa.String(60), nullable=False),
        sa.Column("location", sa.String(60), nullable=False),
        sa.Column("circuit_short_name", sa.String(30), nullable=False),
        sa.Column("circuit_key", sa.Integer),
        sa.Column("year", sa.SmallInteger, nullable=False),
        sa.Column("date_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_end", sa.DateTime(timezone=True)),
        sa.Column("gmt_offset", sa.String(10)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_meetings_year", "meetings", ["year"])

    # --- sessions ---
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_key", sa.Integer, unique=True, nullable=False),
        sa.Column("meeting_id", sa.Integer, sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("session_name", sa.String(30), nullable=False),
        sa.Column("session_type", session_type, nullable=False),
        sa.Column("date_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_end", sa.DateTime(timezone=True)),
        sa.Column("ingested_at", sa.DateTime(timezone=True)),
        sa.Column("ingest_status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_sessions_meeting", "sessions", ["meeting_id"])

    # --- drivers ---
    op.create_table(
        "drivers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("driver_number", sa.SmallInteger, nullable=False),
        sa.Column("full_name", sa.String(60), nullable=False),
        sa.Column("name_acronym", sa.String(3), nullable=False),
        sa.Column("team_name", sa.String(40), nullable=False),
        sa.Column("team_colour", sa.String(6), nullable=False),
        sa.Column("headshot_url", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "driver_number", name="uq_driver_session"),
    )
    op.create_index("idx_drivers_session", "drivers", ["session_id"])

    # --- car_positions ---
    op.create_table(
        "car_positions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("driver_number", sa.SmallInteger, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("x", sa.Float, nullable=False),
        sa.Column("y", sa.Float, nullable=False),
        sa.Column("z", sa.Float),
    )
    op.create_index("idx_car_positions_session_ts", "car_positions", ["session_id", "timestamp"])
    op.create_index("idx_car_positions_driver_ts", "car_positions", ["session_id", "driver_number", "timestamp"])

    # --- car_telemetry ---
    op.create_table(
        "car_telemetry",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("driver_number", sa.SmallInteger, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("speed", sa.SmallInteger, nullable=False),
        sa.Column("throttle", sa.SmallInteger),
        sa.Column("brake", sa.SmallInteger),
        sa.Column("n_gear", sa.SmallInteger),
        sa.Column("rpm", sa.Integer),
        sa.Column("drs", sa.SmallInteger),
    )
    op.create_index("idx_car_telemetry_session_ts", "car_telemetry", ["session_id", "timestamp"])
    op.create_index("idx_car_telemetry_driver_ts", "car_telemetry", ["session_id", "driver_number", "timestamp"])

    # --- weather_samples ---
    op.create_table(
        "weather_samples",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("air_temperature", sa.Float),
        sa.Column("track_temperature", sa.Float),
        sa.Column("humidity", sa.Float),
        sa.Column("pressure", sa.Float),
        sa.Column("wind_speed", sa.Float),
        sa.Column("wind_direction", sa.SmallInteger),
        sa.Column("rainfall", sa.Boolean),
    )
    op.create_index("idx_weather_session_ts", "weather_samples", ["session_id", "timestamp"])

    # --- laps ---
    op.create_table(
        "laps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("driver_number", sa.SmallInteger, nullable=False),
        sa.Column("lap_number", sa.SmallInteger, nullable=False),
        sa.Column("lap_duration", sa.Float),
        sa.Column("duration_sector_1", sa.Float),
        sa.Column("duration_sector_2", sa.Float),
        sa.Column("duration_sector_3", sa.Float),
        sa.Column("i1_speed", sa.SmallInteger),
        sa.Column("i2_speed", sa.SmallInteger),
        sa.Column("st_speed", sa.SmallInteger),
        sa.Column("segments_sector_1", ARRAY(sa.SmallInteger)),
        sa.Column("segments_sector_2", ARRAY(sa.SmallInteger)),
        sa.Column("segments_sector_3", ARRAY(sa.SmallInteger)),
        sa.Column("is_pit_out_lap", sa.Boolean, server_default=sa.text("false")),
        sa.Column("date_start", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("session_id", "driver_number", "lap_number", name="uq_lap"),
    )
    op.create_index("idx_laps_session_driver", "laps", ["session_id", "driver_number"])

    # --- stints ---
    op.create_table(
        "stints",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("driver_number", sa.SmallInteger, nullable=False),
        sa.Column("stint_number", sa.SmallInteger, nullable=False),
        sa.Column("compound", tyre_compound, nullable=False),
        sa.Column("lap_start", sa.SmallInteger, nullable=False),
        sa.Column("lap_end", sa.SmallInteger),
        sa.Column("tyre_age_at_start", sa.SmallInteger, server_default=sa.text("0")),
        sa.UniqueConstraint("session_id", "driver_number", "stint_number", name="uq_stint"),
    )

    # --- race_control_events ---
    op.create_table(
        "race_control_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", race_control_category, nullable=False),
        sa.Column("flag", flag_type),
        sa.Column("scope", sa.String(20)),
        sa.Column("sector", sa.SmallInteger),
        sa.Column("driver_number", sa.SmallInteger),
        sa.Column("lap_number", sa.SmallInteger),
        sa.Column("message", sa.Text, nullable=False),
    )
    op.create_index("idx_race_control_session_ts", "race_control_events", ["session_id", "timestamp"])

    # --- intervals ---
    op.create_table(
        "intervals",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("driver_number", sa.SmallInteger, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gap_to_leader", sa.Float),
        sa.Column("interval_ahead", sa.Float),
    )
    op.create_index("idx_intervals_session_ts", "intervals", ["session_id", "timestamp"])

    # --- positions ---
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("driver_number", sa.SmallInteger, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("position", sa.SmallInteger, nullable=False),
    )
    op.create_index("idx_positions_session_ts", "positions", ["session_id", "timestamp"])

    # --- pit_stops ---
    op.create_table(
        "pit_stops",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("driver_number", sa.SmallInteger, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lap_number", sa.SmallInteger, nullable=False),
        sa.Column("pit_duration", sa.Float),
        sa.Column("stop_duration", sa.Float),
    )
    op.create_index("idx_pit_stops_session", "pit_stops", ["session_id"])

    # --- circuit_geometry ---
    op.create_table(
        "circuit_geometry",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), unique=True, nullable=False),
        sa.Column("total_points", sa.Integer, nullable=False),
        sa.Column("centerline", JSONB, nullable=False),
        sa.Column("segments", JSONB, nullable=False),
        sa.Column("bounds", JSONB, nullable=False),
        sa.Column("total_length", sa.Float, nullable=False),
        sa.Column("source_driver", sa.SmallInteger),
        sa.Column("source_lap", sa.SmallInteger),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- condition_snapshots ---
    op.create_table(
        "condition_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lap_number", sa.SmallInteger),
        sa.Column("weather", JSONB, nullable=False),
        sa.Column("segment_conditions", JSONB, nullable=False),
        sa.Column("rain_zones", JSONB),
    )
    op.create_index("idx_condition_snapshots_session_ts", "condition_snapshots", ["session_id", "timestamp"])

    # --- car_timeline ---
    op.create_table(
        "car_timeline",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("driver_number", sa.SmallInteger, nullable=False),
        sa.Column("x", sa.Float, nullable=False),
        sa.Column("y", sa.Float, nullable=False),
        sa.Column("speed", sa.SmallInteger),
        sa.Column("position", sa.SmallInteger),
        sa.Column("lap_number", sa.SmallInteger),
        sa.Column("compound", tyre_compound),
        sa.Column("tyre_age", sa.SmallInteger),
        sa.Column("drs_active", sa.Boolean, server_default=sa.text("false")),
        sa.Column("in_pit", sa.Boolean, server_default=sa.text("false")),
        sa.Column("segment_id", sa.SmallInteger),
    )
    op.create_index("idx_car_timeline_session_ts", "car_timeline", ["session_id", "timestamp"])
    op.create_index("idx_car_timeline_driver", "car_timeline", ["session_id", "driver_number", "timestamp"])

    # --- insights ---
    op.create_table(
        "insights",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lap_number", sa.SmallInteger),
        sa.Column("severity", insight_severity, nullable=False),
        sa.Column("data_label", data_label, nullable=False),
        sa.Column("segment_id", sa.SmallInteger),
        sa.Column("driver_number", sa.SmallInteger),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("evidence", JSONB),
        sa.Column("confidence", sa.Float),
    )
    op.create_index("idx_insights_session_ts", "insights", ["session_id", "timestamp"])
    op.create_index("idx_insights_category", "insights", ["session_id", "category"])


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("insights")
    op.drop_table("car_timeline")
    op.drop_table("condition_snapshots")
    op.drop_table("circuit_geometry")
    op.drop_table("pit_stops")
    op.drop_table("positions")
    op.drop_table("intervals")
    op.drop_table("race_control_events")
    op.drop_table("stints")
    op.drop_table("laps")
    op.drop_table("weather_samples")
    op.drop_table("car_telemetry")
    op.drop_table("car_positions")
    op.drop_table("drivers")
    op.drop_table("sessions")
    op.drop_table("meetings")

    # Drop ENUMs
    sa.Enum(name="data_label").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="insight_severity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="evolution_trend").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="condition_level").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="race_control_category").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="flag_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tyre_compound").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="session_type").drop(op.get_bind(), checkfirst=True)
