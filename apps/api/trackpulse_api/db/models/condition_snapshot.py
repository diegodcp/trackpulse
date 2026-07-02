from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB

from trackpulse_api.db.base import Base


class ConditionSnapshot(Base):
    __tablename__ = "condition_snapshots"
    __table_args__ = (
        Index("idx_condition_snapshots_session_ts", "session_id", "timestamp"),
    )

    id = Column(BigInteger, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    lap_number = Column(SmallInteger)
    weather = Column(JSONB, nullable=False)
    segment_conditions = Column(JSONB, nullable=False)
    rain_zones = Column(JSONB)
