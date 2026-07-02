from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, SmallInteger

from trackpulse_api.db.base import Base


class WeatherSample(Base):
    __tablename__ = "weather_samples"
    __table_args__ = (
        Index("idx_weather_session_ts", "session_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    air_temperature = Column(Float)
    track_temperature = Column(Float)
    humidity = Column(Float)
    pressure = Column(Float)
    wind_speed = Column(Float)
    wind_direction = Column(SmallInteger)
    rainfall = Column(Boolean)
