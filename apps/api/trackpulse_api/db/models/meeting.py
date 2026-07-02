from sqlalchemy import Column, DateTime, Integer, SmallInteger, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trackpulse_api.db.base import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True)
    meeting_key = Column(Integer, unique=True, nullable=False)
    meeting_name = Column(String(100), nullable=False)
    country_name = Column(String(60), nullable=False)
    location = Column(String(60), nullable=False)
    circuit_short_name = Column(String(30), nullable=False)
    circuit_key = Column(Integer)
    year = Column(SmallInteger, nullable=False, index=True)
    date_start = Column(DateTime(timezone=True), nullable=False)
    date_end = Column(DateTime(timezone=True))
    gmt_offset = Column(String(10))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sessions = relationship("Session", back_populates="meeting")
