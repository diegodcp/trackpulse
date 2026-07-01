from __future__ import annotations

from dataclasses import dataclass


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
