"""add raw event and state tables

Revision ID: 0001_add_raw_event_and_state_tables
Revises: 
Create Date: 2026-07-01 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_add_raw_event_and_state_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raw_openf1_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("topic", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("source_key", sa.String(length=255), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("topic", "source_id", name="uq_raw_openf1_events_topic_source_id"),
    )
    op.create_index("ix_raw_openf1_events_topic", "raw_openf1_events", ["topic"])
    op.create_index("ix_raw_openf1_events_ingested_at", "raw_openf1_events", ["ingested_at"])

    op.create_table(
        "track_segment_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_key", sa.Integer(), nullable=True),
        sa.Column("segment_key", sa.String(length=128), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("value_label", sa.String(length=16), nullable=False, server_default="inferred"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_track_segment_states_session_key", "track_segment_states", ["session_key"])
    op.create_index("ix_track_segment_states_segment_key", "track_segment_states", ["segment_key"])
    op.create_index("ix_track_segment_states_as_of", "track_segment_states", ["as_of"])

    op.create_table(
        "live_insights",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_key", sa.Integer(), nullable=True),
        sa.Column("insight_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("value_label", sa.String(length=16), nullable=False, server_default="inferred"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_live_insights_session_key", "live_insights", ["session_key"])
    op.create_index("ix_live_insights_insight_key", "live_insights", ["insight_key"])
    op.create_index("ix_live_insights_as_of", "live_insights", ["as_of"])


def downgrade() -> None:
    op.drop_index("ix_live_insights_as_of", table_name="live_insights")
    op.drop_index("ix_live_insights_insight_key", table_name="live_insights")
    op.drop_index("ix_live_insights_session_key", table_name="live_insights")
    op.drop_table("live_insights")

    op.drop_index("ix_track_segment_states_as_of", table_name="track_segment_states")
    op.drop_index("ix_track_segment_states_segment_key", table_name="track_segment_states")
    op.drop_index("ix_track_segment_states_session_key", table_name="track_segment_states")
    op.drop_table("track_segment_states")

    op.drop_index("ix_raw_openf1_events_ingested_at", table_name="raw_openf1_events")
    op.drop_index("ix_raw_openf1_events_topic", table_name="raw_openf1_events")
    op.drop_table("raw_openf1_events")
