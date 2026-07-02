from sqlalchemy import Column, Enum, ForeignKey, Integer, SmallInteger, UniqueConstraint

from trackpulse_api.db.base import Base
from trackpulse_api.db.models.enums import TyreCompound


class Stint(Base):
    __tablename__ = "stints"
    __table_args__ = (
        UniqueConstraint("session_id", "driver_number", "stint_number", name="uq_stint"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    driver_number = Column(SmallInteger, nullable=False)
    stint_number = Column(SmallInteger, nullable=False)
    compound = Column(Enum(TyreCompound, name="tyre_compound"), nullable=False)
    lap_start = Column(SmallInteger, nullable=False)
    lap_end = Column(SmallInteger)
    tyre_age_at_start = Column(SmallInteger, default=0)
