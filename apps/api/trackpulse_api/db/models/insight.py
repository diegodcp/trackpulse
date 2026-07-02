from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from trackpulse_api.db.base import Base
from trackpulse_api.db.models.enums import DataLabel, InsightSeverity


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (
        Index("idx_insights_session_ts", "session_id", "timestamp"),
        Index("idx_insights_category", "session_id", "category"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    lap_number = Column(SmallInteger)
    severity = Column(Enum(InsightSeverity, name="insight_severity"), nullable=False)
    data_label = Column(Enum(DataLabel, name="data_label"), nullable=False)
    segment_id = Column(SmallInteger)
    driver_number = Column(SmallInteger)
    category = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    evidence = Column(JSONB)
    confidence = Column(Float)
