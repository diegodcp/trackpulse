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


# --- Compact chunked format ---


class DriverMetaSchema(BaseModel):
    driver_number: int
    name_acronym: str
    team_colour: str


class DriverPositionsSchema(BaseModel):
    x: list[float | None]
    y: list[float | None]
    speed: list[int | None]
    position: list[int | None]
    lap: list[int | None]


class CompactChunkResponse(BaseModel):
    session_key: int
    total_duration_seconds: float
    target_hz: float
    total_chunks: int
    chunk_index: int
    chunk_start_seconds: float
    chunk_end_seconds: float
    frame_count: int
    drivers: list[DriverMetaSchema]
    elapsed: list[float]
    positions: dict[str, DriverPositionsSchema]


class TimelineMetaResponse(BaseModel):
    """Lightweight metadata for a car timeline — no position data."""

    session_key: int
    total_duration_seconds: float
    target_hz: float
    total_chunks: int
    chunk_seconds: float
    drivers: list[DriverMetaSchema]

