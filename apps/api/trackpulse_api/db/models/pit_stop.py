from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, SmallInteger

from trackpulse_api.db.base import Base


class PitStop(Base):
    __tablename__ = "pit_stops"
    __table_args__ = (
        Index("idx_pit_stops_session", "session_id"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    driver_number = Column(SmallInteger, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    lap_number = Column(SmallInteger, nullable=False)
    pit_duration = Column(Float)
    stop_duration = Column(Float)
