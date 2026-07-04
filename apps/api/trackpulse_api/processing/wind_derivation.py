"""Pure wind derivation — derives per-segment wind characteristics from global wind.

This module contains ONLY pure functions — no I/O, no DB, no HTTP.
Given a global wind measurement and circuit geometry, it computes per-segment
wind classification (headwind/tailwind/crosswind) based on track heading.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np


class WindClass(str, Enum):
    HEADWIND = "headwind"
    TAILWIND = "tailwind"
    CROSSWIND_LEFT = "crosswind_left"
    CROSSWIND_RIGHT = "crosswind_right"


@dataclass(frozen=True)
class SegmentWind:
    segment_id: int
    wind_class: WindClass
    relative_angle: float  # Signed angle between wind direction and track heading (-180 to 180°)
    effective_speed: float  # Dominant component of wind along/across track (m/s)
    headwind_component: float  # Positive = headwind (opposing), negative = tailwind (assisting)
    crosswind_component: float  # Signed crosswind: positive = from right, negative = from left


def compute_track_heading(points: list[dict], idx: int, lookahead: int = 5) -> float:
    """Compute track heading (direction cars travel) at a given point index.

    Uses lookahead points for stability to smooth out noise from individual
    point-to-point deltas.

    Args:
        points: Ordered circuit centerline points with 'x' and 'y' keys.
        idx: Index at which to compute heading.
        lookahead: Number of points ahead to use for direction vector.

    Returns:
        Heading in degrees (0-360, 0=North, 90=East).
    """
    next_idx = min(idx + lookahead, len(points) - 1)
    if next_idx == idx:
        # At the end — look backwards
        prev_idx = max(idx - lookahead, 0)
        dx = points[idx]["x"] - points[prev_idx]["x"]
        dy = points[idx]["y"] - points[prev_idx]["y"]
    else:
        dx = points[next_idx]["x"] - points[idx]["x"]
        dy = points[next_idx]["y"] - points[idx]["y"]

    # atan2(dx, dy) gives angle from North (Y-axis), clockwise positive
    angle_rad = np.arctan2(dx, dy)
    heading = float(np.degrees(angle_rad)) % 360
    return heading


def angle_difference(from_deg: float, to_deg: float) -> float:
    """Compute signed angle difference (from_deg - to_deg), normalized to [-180, 180].

    Handles wrap-around correctly across the 0°/360° boundary.

    Args:
        from_deg: Source angle in degrees.
        to_deg: Target angle in degrees.

    Returns:
        Signed difference in range [-180, 180].
    """
    diff = (from_deg - to_deg + 180) % 360 - 180
    return diff


def derive_segment_wind(
    wind_speed: float,
    wind_direction: int,
    circuit_points: list[dict],
    segments: list[dict],
) -> list[SegmentWind]:
    """Derive per-segment wind characteristics from global wind measurement.

    For each segment:
    1. Compute track heading at segment midpoint (direction cars travel)
    2. Compute angle between wind source direction and track heading
    3. Decompose wind into headwind and crosswind components
    4. Classify: headwind (±45°), tailwind (±45° from behind), crosswind otherwise

    Wind direction convention (meteorological):
    - 0° = wind comes FROM North (blows southward)
    - 90° = wind comes FROM East (blows westward)
    - Direction is where the wind comes FROM, not where it goes

    Track heading convention:
    - 0° = track goes North
    - 90° = track goes East
    - Derived from consecutive point deltas

    Args:
        wind_speed: Global wind speed in m/s.
        wind_direction: Where wind comes from (0-359°).
        circuit_points: Ordered centerline points as dicts with 'x', 'y' keys.
        segments: Segment boundaries as dicts with 'id', 'start_idx', 'end_idx' keys.

    Returns:
        List of SegmentWind, one per segment.
    """
    results: list[SegmentWind] = []

    for segment in segments:
        # Get midpoint of segment
        mid_idx = (segment["start_idx"] + segment["end_idx"]) // 2

        # Compute track heading at midpoint
        heading = compute_track_heading(circuit_points, mid_idx)

        # Compute relative angle: wind_from - track_heading
        # Positive means wind is coming from the right of the car's travel direction
        relative = angle_difference(wind_direction, heading)

        # Decompose into head/cross components
        # headwind_component > 0 means wind opposes car movement (headwind)
        headwind = wind_speed * float(np.cos(np.radians(relative)))
        crosswind = wind_speed * float(np.sin(np.radians(relative)))

        # Classify based on absolute relative angle
        abs_relative = abs(relative)
        if abs_relative <= 45:
            wind_class = WindClass.HEADWIND
        elif abs_relative >= 135:
            wind_class = WindClass.TAILWIND
        elif relative > 0:
            wind_class = WindClass.CROSSWIND_RIGHT
        else:
            wind_class = WindClass.CROSSWIND_LEFT

        # Effective speed is the dominant component
        if abs_relative <= 45 or abs_relative >= 135:
            effective = abs(headwind)
        else:
            effective = abs(crosswind)

        results.append(
            SegmentWind(
                segment_id=segment["id"],
                wind_class=wind_class,
                relative_angle=round(relative, 2),
                effective_speed=round(effective, 3),
                headwind_component=round(headwind, 3),
                crosswind_component=round(crosswind, 3),
            )
        )

    return results
