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
