from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, Float, ForeignKey, Index, Integer, SmallInteger

from trackpulse_api.db.base import Base
from trackpulse_api.db.models.enums import TyreCompound


class CarTimeline(Base):
    __tablename__ = "car_timeline"
    __table_args__ = (
        Index("idx_car_timeline_session_ts", "session_id", "timestamp"),
        Index("idx_car_timeline_driver", "session_id", "driver_number", "timestamp"),
    )

    id = Column(BigInteger, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    driver_number = Column(SmallInteger, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    speed = Column(SmallInteger)
    position = Column(SmallInteger)
    lap_number = Column(SmallInteger)
    compound = Column(Enum(TyreCompound, name="tyre_compound", create_type=False))
    tyre_age = Column(SmallInteger)
    drs_active = Column(Boolean, default=False)
    in_pit = Column(Boolean, default=False)
    segment_id = Column(SmallInteger)
