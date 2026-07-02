from pydantic import BaseModel


class CarFrameSchema(BaseModel):
    driver_number: int
    x: float
    y: float
    speed: int | None = None
    position: int | None = None
    lap_number: int | None = None
    name_acronym: str
    team_colour: str


class TimelineFrameSchema(BaseModel):
    timestamp: str
    elapsed_seconds: float
    cars: list[CarFrameSchema]


class CarTimelineResponse(BaseModel):
    session_key: int
    total_frames: int
    duration_seconds: float
    target_hz: float
    frames: list[TimelineFrameSchema]
