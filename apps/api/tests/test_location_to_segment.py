from __future__ import annotations

import pytest

from trackpulse_api.inference.location import CircuitPoint, assign_nearest_segment, TrackSegmentPath
from trackpulse_api.state.track_model import BAHRAIN_SEGMENT_PATHS


def _segments() -> list[TrackSegmentPath]:
    return list(BAHRAIN_SEGMENT_PATHS)


def _point_inside(segment_id: str, index: int = 10) -> CircuitPoint:
    segment = next(item for item in BAHRAIN_SEGMENT_PATHS if item.segment_id == segment_id)
    point = segment.path[index]
    return CircuitPoint(x=point.x, y=point.y)


def test_assign_nearest_segment_exact_point() -> None:
    assignment = assign_nearest_segment(
        point=_point_inside("bh-s01"),
        segments=_segments(),
        low_confidence_distance=25.0,
    )

    assert assignment.segment_id == "bh-s01"
    assert assignment.distance == pytest.approx(0.0)
    assert assignment.confidence == pytest.approx(1.0)


def test_assign_nearest_segment_near_point() -> None:
    reference = _point_inside("bh-s08", index=12)
    assignment = assign_nearest_segment(
        point=CircuitPoint(x=reference.x + 2.0, y=reference.y - 1.5),
        segments=_segments(),
        low_confidence_distance=25.0,
    )

    assert assignment.segment_id == "bh-s08"
    assert assignment.distance is not None
    assert assignment.distance > 0.0
    assert 0.1 < assignment.confidence < 1.0


def test_assign_nearest_segment_far_point_has_low_confidence() -> None:
    assignment = assign_nearest_segment(
        point=CircuitPoint(x=-1000.0, y=-1000.0),
        segments=_segments(),
        low_confidence_distance=25.0,
    )

    assert assignment.segment_id in {segment.segment_id for segment in BAHRAIN_SEGMENT_PATHS}
    assert assignment.distance is not None
    assert assignment.distance > 1000.0
    assert assignment.confidence == pytest.approx(0.1)


def test_assign_nearest_segment_real_geometry_examples() -> None:
    assignment_s04 = assign_nearest_segment(
        point=_point_inside("bh-s04", index=8),
        segments=_segments(),
        low_confidence_distance=25.0,
    )
    assignment_s14 = assign_nearest_segment(
        point=_point_inside("bh-s14", index=9),
        segments=_segments(),
        low_confidence_distance=25.0,
    )

    assert assignment_s04.segment_id == "bh-s04"
    assert assignment_s04.distance == pytest.approx(0.0)
    assert assignment_s14.segment_id == "bh-s14"
    assert assignment_s14.distance == pytest.approx(0.0)


def test_assign_nearest_segment_empty_map() -> None:
    assignment = assign_nearest_segment(
        point=CircuitPoint(x=1.0, y=2.0),
        segments=[],
        low_confidence_distance=5.0,
    )

    assert assignment.segment_id is None
    assert assignment.distance is None
    assert assignment.confidence == pytest.approx(0.0)
