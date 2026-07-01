from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionDiscoveryQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    year: int = Field(ge=1950, le=2100)
    country_name: str = Field(min_length=1)
    session_name: str = Field(min_length=1)


class OpenF1Session(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    session_key: int
    session_name: str
    date_start: datetime | None = None
    meeting_key: int | None = None
    country_name: str | None = None
    year: int | None = None


class OpenF1Weather(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    date: datetime
    session_key: int | None = None
    meeting_key: int | None = None
    air_temperature: float | None = None
    track_temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    rainfall: bool | None = None
    wind_direction: int | None = None
    wind_speed: float | None = None


class OpenF1Location(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    date: datetime
    driver_number: int
    session_key: int | None = None
    meeting_key: int | None = None
    x: float
    y: float
    z: float | None = None
