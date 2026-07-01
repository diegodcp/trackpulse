from __future__ import annotations

from dataclasses import dataclass

from ..inference import CircuitPoint, TrackSegmentPath


@dataclass(frozen=True)
class TrackSegmentModel:
    segment_id: str
    direction_deg: float


# Assumption (TP-BH-0015): backend replay uses the same stable, stylized Bahrain
# segment IDs as the frontend fixture so segment-level overlays remain aligned.
BAHRAIN_TRACK_SEGMENTS: tuple[TrackSegmentModel, ...] = (
    TrackSegmentModel(segment_id="bh-s01", direction_deg=162.0),
    TrackSegmentModel(segment_id="bh-s02", direction_deg=130.0),
    TrackSegmentModel(segment_id="bh-s03", direction_deg=112.0),
    TrackSegmentModel(segment_id="bh-s04", direction_deg=88.0),
    TrackSegmentModel(segment_id="bh-s05", direction_deg=84.0),
    TrackSegmentModel(segment_id="bh-s06", direction_deg=80.0),
    TrackSegmentModel(segment_id="bh-s07", direction_deg=71.0),
    TrackSegmentModel(segment_id="bh-s08", direction_deg=35.0),
    TrackSegmentModel(segment_id="bh-s09", direction_deg=344.0),
    TrackSegmentModel(segment_id="bh-s10", direction_deg=306.0),
    TrackSegmentModel(segment_id="bh-s11", direction_deg=286.0),
    TrackSegmentModel(segment_id="bh-s12", direction_deg=281.0),
    TrackSegmentModel(segment_id="bh-s13", direction_deg=277.0),
    TrackSegmentModel(segment_id="bh-s14", direction_deg=261.0),
    TrackSegmentModel(segment_id="bh-s15", direction_deg=236.0),
    TrackSegmentModel(segment_id="bh-s16", direction_deg=200.0),
)

BAHRAIN_MAP_WIDTH: int = 1200
BAHRAIN_MAP_HEIGHT: int = 700
BAHRAIN_MAP_PADDING: int = 120

# Assumption (TP-BH-0016): reuse the same stylized segment polylines as the
# frontend fixture for nearest-segment traffic assignment.
BAHRAIN_SEGMENT_PATHS: tuple[TrackSegmentPath, ...] = (
    TrackSegmentPath(
        segment_id="bh-s01",
        path=(
            CircuitPoint(x=170.0, y=380.0),
            CircuitPoint(x=210.0, y=500.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s02",
        path=(
            CircuitPoint(x=210.0, y=500.0),
            CircuitPoint(x=280.0, y=560.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s03",
        path=(
            CircuitPoint(x=280.0, y=560.0),
            CircuitPoint(x=350.0, y=590.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s04",
        path=(
            CircuitPoint(x=350.0, y=590.0),
            CircuitPoint(x=470.0, y=605.0),
            CircuitPoint(x=570.0, y=600.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s05",
        path=(
            CircuitPoint(x=570.0, y=600.0),
            CircuitPoint(x=680.0, y=590.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s06",
        path=(
            CircuitPoint(x=680.0, y=590.0),
            CircuitPoint(x=850.0, y=560.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s07",
        path=(
            CircuitPoint(x=850.0, y=560.0),
            CircuitPoint(x=1020.0, y=500.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s08",
        path=(
            CircuitPoint(x=1020.0, y=500.0),
            CircuitPoint(x=1075.0, y=420.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s09",
        path=(
            CircuitPoint(x=1075.0, y=420.0),
            CircuitPoint(x=1050.0, y=330.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s10",
        path=(
            CircuitPoint(x=1050.0, y=330.0),
            CircuitPoint(x=940.0, y=250.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s11",
        path=(
            CircuitPoint(x=940.0, y=250.0),
            CircuitPoint(x=840.0, y=220.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s12",
        path=(
            CircuitPoint(x=840.0, y=220.0),
            CircuitPoint(x=760.0, y=205.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s13",
        path=(
            CircuitPoint(x=760.0, y=205.0),
            CircuitPoint(x=640.0, y=190.0),
            CircuitPoint(x=520.0, y=175.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s14",
        path=(
            CircuitPoint(x=520.0, y=175.0),
            CircuitPoint(x=325.0, y=205.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s15",
        path=(
            CircuitPoint(x=325.0, y=205.0),
            CircuitPoint(x=205.0, y=285.0),
        ),
    ),
    TrackSegmentPath(
        segment_id="bh-s16",
        path=(
            CircuitPoint(x=205.0, y=285.0),
            CircuitPoint(x=170.0, y=380.0),
        ),
    ),
)
