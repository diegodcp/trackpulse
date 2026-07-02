from datetime import datetime

from pydantic import BaseModel


class SessionInfo(BaseModel):
    session_key: int
    session_name: str
    session_type: str
    date_start: datetime
    date_end: datetime | None = None

    model_config = {"from_attributes": True}


class MeetingWithSessions(BaseModel):
    meeting_key: int
    meeting_name: str
    country_name: str
    location: str
    circuit_short_name: str
    year: int
    date_start: datetime
    sessions: list[SessionInfo]

    model_config = {"from_attributes": True}
