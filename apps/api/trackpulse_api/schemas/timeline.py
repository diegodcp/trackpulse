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


class WeatherStateSchema(BaseModel):
    air_temperature: float
    track_temperature: float
    humidity: float
    wind_speed: float
    wind_direction: int
    rainfall: bool


class TimelineFrameSchema(BaseModel):
    timestamp: str
    elapsed_seconds: float
    cars: list[CarFrameSchema]
    weather: WeatherStateSchema | None = None


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


class SegmentWindSchema(BaseModel):
    """Per-segment wind characteristics derived from global wind + track heading."""

    segment_id: int
    wind_class: str  # headwind / tailwind / crosswind_left / crosswind_right
    effective_speed: float  # Dominant wind component magnitude (m/s)
    headwind_component: float  # Positive = opposing car, negative = assisting
    crosswind_component: float  # Positive = from right, negative = from left


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
    weather: list[WeatherStateSchema] | None = None
    segment_wind: list[list[SegmentWindSchema]] | None = None
    race_start_elapsed_seconds: float | None = None


class TimelineMetaResponse(BaseModel):
    """Lightweight metadata for a car timeline — no position data."""

    session_key: int
    total_duration_seconds: float
    target_hz: float
    total_chunks: int
    chunk_seconds: float
    drivers: list[DriverMetaSchema]
    race_start_elapsed_seconds: float | None = None

