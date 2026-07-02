from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY

from trackpulse_api.db.base import Base


class Lap(Base):
    __tablename__ = "laps"
    __table_args__ = (
        UniqueConstraint("session_id", "driver_number", "lap_number", name="uq_lap"),
        Index("idx_laps_session_driver", "session_id", "driver_number"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    driver_number = Column(SmallInteger, nullable=False)
    lap_number = Column(SmallInteger, nullable=False)
    lap_duration = Column(Float)
    duration_sector_1 = Column(Float)
    duration_sector_2 = Column(Float)
    duration_sector_3 = Column(Float)
    i1_speed = Column(SmallInteger)
    i2_speed = Column(SmallInteger)
    st_speed = Column(SmallInteger)
    segments_sector_1 = Column(ARRAY(SmallInteger))
    segments_sector_2 = Column(ARRAY(SmallInteger))
    segments_sector_3 = Column(ARRAY(SmallInteger))
    is_pit_out_lap = Column(Boolean, default=False)
    date_start = Column(DateTime(timezone=True))
