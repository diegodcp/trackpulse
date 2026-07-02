from pydantic import BaseModel


class PointSchema(BaseModel):
    x: float
    y: float
    cumulative_dist: float


class SegmentSchema(BaseModel):
    id: int
    start_idx: int
    end_idx: int
    sector: int
    start_dist: float
    end_dist: float


class BoundsSchema(BaseModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class CircuitGeometryResponse(BaseModel):
    session_key: int
    total_points: int
    total_length: float
    bounds: BoundsSchema
    points: list[PointSchema]
    segments: list[SegmentSchema]
    source_driver: int | None
    source_lap: int | None
