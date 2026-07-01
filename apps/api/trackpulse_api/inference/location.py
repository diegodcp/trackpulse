from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable, Sequence


@dataclass(frozen=True)
class CircuitPoint:
    x: float
    y: float


@dataclass(frozen=True)
class TrackSegmentPath:
    segment_id: str
    path: tuple[CircuitPoint, ...]


@dataclass(frozen=True)
class SegmentAssignment:
    segment_id: str | None
    distance: float | None
    confidence: float


def _distance_point_to_segment(point: CircuitPoint, start: CircuitPoint, end: CircuitPoint) -> float:
    vx = end.x - start.x
    vy = end.y - start.y
    wx = point.x - start.x
    wy = point.y - start.y
    length_sq = (vx * vx) + (vy * vy)

    if length_sq == 0.0:
        return hypot(point.x - start.x, point.y - start.y)

    projection = ((wx * vx) + (wy * vy)) / length_sq
    clamped_projection = max(0.0, min(1.0, projection))

    closest_x = start.x + clamped_projection * vx
    closest_y = start.y + clamped_projection * vy
    return hypot(point.x - closest_x, point.y - closest_y)


def _distance_point_to_polyline(point: CircuitPoint, polyline: Sequence[CircuitPoint]) -> float:
    if not polyline:
        return float("inf")

    if len(polyline) == 1:
        only = polyline[0]
        return hypot(point.x - only.x, point.y - only.y)

    nearest = float("inf")
    for start, end in zip(polyline[:-1], polyline[1:]):
        nearest = min(nearest, _distance_point_to_segment(point, start, end))

    return nearest


def _confidence_from_distance(distance: float, low_confidence_distance: float) -> float:
    if low_confidence_distance <= 0.0:
        raise ValueError("low_confidence_distance must be greater than 0")

    if distance >= low_confidence_distance:
        return 0.1

    ratio = distance / low_confidence_distance
    return round(1.0 - (0.9 * ratio), 3)


def assign_nearest_segment(
    *,
    point: CircuitPoint,
    segments: Iterable[TrackSegmentPath],
    low_confidence_distance: float = 25.0,
) -> SegmentAssignment:
    """Assign a point to the nearest segment path.

    Assumption: distance units are the same units used by the input map
    coordinate system. Confidence decays linearly from 1.0 at distance 0 to 0.1
    at low_confidence_distance and stays low afterwards.
    """
    nearest_segment_id: str | None = None
    nearest_distance = float("inf")

    for segment in segments:
        distance = _distance_point_to_polyline(point, segment.path)
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_segment_id = segment.segment_id
        elif distance == nearest_distance and nearest_segment_id is not None and segment.segment_id < nearest_segment_id:
            # Stable tie-break for deterministic assignments.
            nearest_segment_id = segment.segment_id

    if nearest_segment_id is None or nearest_distance == float("inf"):
        return SegmentAssignment(segment_id=None, distance=None, confidence=0.0)

    return SegmentAssignment(
        segment_id=nearest_segment_id,
        distance=nearest_distance,
        confidence=_confidence_from_distance(nearest_distance, low_confidence_distance),
    )
