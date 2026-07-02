from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Index, Integer, SmallInteger

from trackpulse_api.db.base import Base


class CarPosition(Base):
    __tablename__ = "car_positions"
    __table_args__ = (
        Index("idx_car_positions_session_ts", "session_id", "timestamp"),
        Index("idx_car_positions_driver_ts", "session_id", "driver_number", "timestamp"),
    )

    id = Column(BigInteger, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    driver_number = Column(SmallInteger, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float)
