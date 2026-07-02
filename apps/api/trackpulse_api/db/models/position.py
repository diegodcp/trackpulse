from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, SmallInteger

from trackpulse_api.db.base import Base


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        Index("idx_positions_session_ts", "session_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    driver_number = Column(SmallInteger, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    position = Column(SmallInteger, nullable=False)
