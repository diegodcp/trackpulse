from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Index, Integer, SmallInteger

from trackpulse_api.db.base import Base


class Interval(Base):
    __tablename__ = "intervals"
    __table_args__ = (
        Index("idx_intervals_session_ts", "session_id", "timestamp"),
    )

    id = Column(BigInteger, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    driver_number = Column(SmallInteger, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    gap_to_leader = Column(Float)
    interval_ahead = Column(Float)
