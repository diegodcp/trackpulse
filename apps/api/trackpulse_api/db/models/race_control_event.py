from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, SmallInteger, String, Text

from trackpulse_api.db.base import Base
from trackpulse_api.db.models.enums import FlagType, RaceControlCategory


class RaceControlEvent(Base):
    __tablename__ = "race_control_events"
    __table_args__ = (
        Index("idx_race_control_session_ts", "session_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    category = Column(
        Enum(RaceControlCategory, name="race_control_category", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    flag = Column(Enum(FlagType, name="flag_type", values_callable=lambda e: [x.value for x in e]))
    scope = Column(String(20))
    sector = Column(SmallInteger)
    driver_number = Column(SmallInteger)
    lap_number = Column(SmallInteger)
    message = Column(Text, nullable=False)
