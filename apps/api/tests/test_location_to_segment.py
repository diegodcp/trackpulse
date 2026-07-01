from __future__ import annotations

import pytest

from trackpulse_api.inference.location import CircuitPoint, assign_nearest_segment, TrackSegmentPath


def _segments() -> list[TrackSegmentPath]:
    return [
        TrackSegmentPath(
            segment_id="s01",
            path=(CircuitPoint(x=0.0, y=0.0), CircuitPoint(x=10.0, y=0.0)),
        ),
        TrackSegmentPath(
            segment_id="s02",
            path=(CircuitPoint(x=0.0, y=10.0), CircuitPoint(x=10.0, y=10.0)),
        ),
    ]


def test_assign_nearest_segment_exact_point() -> None:
    assignment = assign_nearest_segment(
        point=CircuitPoint(x=4.0, y=0.0),
        segments=_segments(),
        low_confidence_distance=5.0,
    )

    assert assignment.segment_id == "s01"
    assert assignment.distance == pytest.approx(0.0)
    assert assignment.confidence == pytest.approx(1.0)


def test_assign_nearest_segment_near_point() -> None:
    assignment = assign_nearest_segment(
        point=CircuitPoint(x=4.0, y=1.0),
        segments=_segments(),
        low_confidence_distance=5.0,
    )

    assert assignment.segment_id == "s01"
    assert assignment.distance == pytest.approx(1.0)
    assert 0.1 < assignment.confidence < 1.0


def test_assign_nearest_segment_far_point_has_low_confidence() -> None:
    assignment = assign_nearest_segment(
        point=CircuitPoint(x=100.0, y=100.0),
        segments=_segments(),
        low_confidence_distance=5.0,
    )

    assert assignment.segment_id in {"s01", "s02"}
    assert assignment.distance is not None
    assert assignment.distance > 100.0
    assert assignment.confidence == pytest.approx(0.1)


def test_assign_nearest_segment_empty_map() -> None:
    assignment = assign_nearest_segment(
        point=CircuitPoint(x=1.0, y=2.0),
        segments=[],
        low_confidence_distance=5.0,
    )

    assert assignment.segment_id is None
    assert assignment.distance is None
    assert assignment.confidence == pytest.approx(0.0)
