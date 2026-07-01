from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RawOpenF1Event(Base):
    __tablename__ = "raw_openf1_events"
    __table_args__ = (
        UniqueConstraint("topic", "source_id", name="uq_raw_openf1_events_topic_source_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    topic: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class TrackSegmentState(Base):
    __tablename__ = "track_segment_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_key: Mapped[int | None] = mapped_column(nullable=True, index=True)
    segment_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    value_label: Mapped[str] = mapped_column(String(16), nullable=False, default="inferred")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LiveInsight(Base):
    __tablename__ = "live_insights"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_key: Mapped[int | None] = mapped_column(nullable=True, index=True)
    insight_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    value_label: Mapped[str] = mapped_column(String(16), nullable=False, default="inferred")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
