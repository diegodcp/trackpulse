from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from trackpulse_api.db.base import Base


class CircuitGeometry(Base):
    __tablename__ = "circuit_geometry"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), unique=True, nullable=False)
    total_points = Column(Integer, nullable=False)
    centerline = Column(JSONB, nullable=False)
    segments = Column(JSONB, nullable=False)
    bounds = Column(JSONB, nullable=False)
    total_length = Column(Float, nullable=False)
    source_driver = Column(SmallInteger)
    source_lap = Column(SmallInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
