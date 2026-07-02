from sqlalchemy import Column, DateTime, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trackpulse_api.db.base import Base


class Driver(Base):
    __tablename__ = "drivers"
    __table_args__ = (
        UniqueConstraint("session_id", "driver_number", name="uq_driver_session"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    driver_number = Column(SmallInteger, nullable=False)
    full_name = Column(String(60), nullable=False)
    name_acronym = Column(String(3), nullable=False)
    team_name = Column(String(40), nullable=False)
    team_colour = Column(String(6), nullable=False)
    headshot_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session", back_populates="drivers")
