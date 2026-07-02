from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trackpulse_api.db.base import Base
from trackpulse_api.db.models.enums import SessionType


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    session_key = Column(Integer, unique=True, nullable=False)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    session_name = Column(String(30), nullable=False)
    session_type = Column(
        Enum(SessionType, name="session_type", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    date_start = Column(DateTime(timezone=True), nullable=False)
    date_end = Column(DateTime(timezone=True))
    ingested_at = Column(DateTime(timezone=True))
    ingest_status = Column(String(20), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meeting = relationship("Meeting", back_populates="sessions")
    drivers = relationship("Driver", back_populates="session")
