from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians


@dataclass(frozen=True)
class WindProjection:
    relative_angle_deg: float | None
    wind_class: str
    strength_score: float | None


def _normalize_angle_deg(angle_deg: float) -> float:
    return ((angle_deg + 180.0) % 360.0) - 180.0


def _wind_class_from_relative_angle(relative_angle_deg: float | None) -> str:
    if relative_angle_deg is None:
        return "unknown"

    absolute_angle = abs(relative_angle_deg)
    if absolute_angle <= 30.0:
        return "headwind"
    if absolute_angle >= 150.0:
        return "tailwind"
    if relative_angle_deg < 0.0:
        return "crosswind_left"
    return "crosswind_right"


def _strength_score(wind_speed_ms: float, relative_angle_deg: float) -> float:
    # Assumption: strength is the absolute along-segment wind component normalized
    # to 0..100, with 20 m/s treated as maximum reference wind speed.
    along_segment_component = abs(wind_speed_ms * cos(radians(relative_angle_deg)))
    return round(min(100.0, (along_segment_component / 20.0) * 100.0), 1)


def project_wind_projection(
    *,
    wind_direction_deg: float | None,
    wind_speed_ms: float | None,
    segment_direction_deg: float | None,
) -> WindProjection:
    """Project track-level wind onto a segment heading.

    Convention assumption (documented for TP-LAYER-02): wind direction follows the
    meteorological standard (direction the wind comes from, clockwise from north).
    Segment direction is the travel heading (direction the car goes to, clockwise
    from north). A relative angle of 0 means headwind, and +/-180 means tailwind.

    This function is pure and returns Derived values only.
    """
    if wind_direction_deg is None or wind_speed_ms is None or segment_direction_deg is None:
        return WindProjection(relative_angle_deg=None, wind_class="unknown", strength_score=None)

    relative_angle_deg = round(_normalize_angle_deg(wind_direction_deg - segment_direction_deg), 1)
    return WindProjection(
        relative_angle_deg=relative_angle_deg,
        wind_class=_wind_class_from_relative_angle(relative_angle_deg),
        strength_score=_strength_score(wind_speed_ms, relative_angle_deg),
    )
