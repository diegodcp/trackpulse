from __future__ import annotations

import pytest

from trackpulse_api.inference.traffic import CarSegmentState, compute_traffic_scores


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEGMENT_ORDER = ["s01", "s02", "s03", "s04", "s05"]


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


def test_empty_track_returns_empty_dict() -> None:
    """No cars → no segment scores."""
    scores = compute_traffic_scores([], _SEGMENT_ORDER)
    assert scores == {}


def test_empty_segment_order_returns_empty_dict() -> None:
    """No segments defined → nothing to score."""
    car = CarSegmentState(segment_id="s01")
    scores = compute_traffic_scores([car], [])
    assert scores == {}


def test_car_with_unknown_segment_id_is_ignored() -> None:
    """Cars assigned to segments not in segment_order are silently excluded."""
    car = CarSegmentState(segment_id="unknown_seg")
    scores = compute_traffic_scores([car], _SEGMENT_ORDER)
    assert scores == {}


# ---------------------------------------------------------------------------
# Normal distribution — one car per segment
# ---------------------------------------------------------------------------


def test_normal_distribution_single_car_per_segment() -> None:
    """
    One car in s03, no close interval.

    Expected contributions
    ----------------------
    s03 (same):      20.0
    s02 (adjacent):  10.0
    s04 (adjacent):  10.0
    """
    car = CarSegmentState(segment_id="s03")
    scores = compute_traffic_scores([car], _SEGMENT_ORDER)

    assert scores.get("s03") == pytest.approx(20.0)
    assert scores.get("s02") == pytest.approx(10.0)
    assert scores.get("s04") == pytest.approx(10.0)
    # Non-affected segments are absent (or zero if caller defaults)
    assert "s01" not in scores
    assert "s05" not in scores


def test_circuit_wraps_first_and_last_segments_are_adjacent() -> None:
    """The last segment should be adjacent to the first (closed loop)."""
    car_first = CarSegmentState(segment_id="s01")
    car_last = CarSegmentState(segment_id="s05")

    scores_first = compute_traffic_scores([car_first], _SEGMENT_ORDER)
    scores_last = compute_traffic_scores([car_last], _SEGMENT_ORDER)

    # s05 is adjacent to s01, so placing a car in s01 should affect s05.
    assert scores_first.get("s05") == pytest.approx(10.0)
    # s01 is adjacent to s05, so placing a car in s05 should affect s01.
    assert scores_last.get("s01") == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Cluster — multiple cars in the same segment
# ---------------------------------------------------------------------------


def test_cluster_two_cars_same_segment() -> None:
    """
    Two cars in s02, no close interval.

    Expected contributions
    ----------------------
    s02 (same × 2):          40.0
    s01 (adjacent × 2):      20.0
    s03 (adjacent × 2):      20.0
    """
    cars = [
        CarSegmentState(segment_id="s02"),
        CarSegmentState(segment_id="s02"),
    ]
    scores = compute_traffic_scores(cars, _SEGMENT_ORDER)

    assert scores.get("s02") == pytest.approx(40.0)
    assert scores.get("s01") == pytest.approx(20.0)
    assert scores.get("s03") == pytest.approx(20.0)


def test_two_cars_in_adjacent_segments_accumulate_scores() -> None:
    """
    Car A in s02, car B in s03.

    s02: 20 (A same) + 10 (B adjacent from s03) = 30
    s03: 10 (A adjacent from s02) + 20 (B same) = 30
    s01: 10 (A adjacent)
    s04: 10 (B adjacent)
    """
    cars = [
        CarSegmentState(segment_id="s02"),
        CarSegmentState(segment_id="s03"),
    ]
    scores = compute_traffic_scores(cars, _SEGMENT_ORDER)

    assert scores.get("s02") == pytest.approx(30.0)
    assert scores.get("s03") == pytest.approx(30.0)
    assert scores.get("s01") == pytest.approx(10.0)
    assert scores.get("s04") == pytest.approx(10.0)
    assert "s05" not in scores


# ---------------------------------------------------------------------------
# Close interval pressure bonus
# ---------------------------------------------------------------------------


def test_close_interval_adds_pressure_to_own_segment() -> None:
    """
    A car with interval_ahead_s ≤ 1.0 gains a pressure bonus on its segment.

    s02 score: 20 (same) + 15 (pressure) = 35
    """
    car = CarSegmentState(segment_id="s02", interval_ahead_s=0.8)
    scores = compute_traffic_scores([car], _SEGMENT_ORDER)

    assert scores.get("s02") == pytest.approx(35.0)


def test_interval_exactly_at_threshold_adds_pressure() -> None:
    """interval_ahead_s == 1.0 is within the threshold and triggers the bonus."""
    car = CarSegmentState(segment_id="s02", interval_ahead_s=1.0)
    scores = compute_traffic_scores([car], _SEGMENT_ORDER)

    assert scores.get("s02") == pytest.approx(35.0)


def test_interval_above_threshold_no_pressure_bonus() -> None:
    """interval_ahead_s > 1.0 does NOT trigger the pressure bonus."""
    car = CarSegmentState(segment_id="s02", interval_ahead_s=1.1)
    scores = compute_traffic_scores([car], _SEGMENT_ORDER)

    assert scores.get("s02") == pytest.approx(20.0)


def test_none_interval_no_pressure_bonus() -> None:
    """interval_ahead_s of None (e.g. race leader) does not add pressure."""
    car = CarSegmentState(segment_id="s02", interval_ahead_s=None)
    scores = compute_traffic_scores([car], _SEGMENT_ORDER)

    assert scores.get("s02") == pytest.approx(20.0)


def test_zero_interval_no_pressure_bonus() -> None:
    """interval_ahead_s of 0.0 is treated as no valid gap and adds no bonus."""
    car = CarSegmentState(segment_id="s02", interval_ahead_s=0.0)
    scores = compute_traffic_scores([car], _SEGMENT_ORDER)

    assert scores.get("s02") == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Clamp to [0, 100]
# ---------------------------------------------------------------------------


def test_score_clamped_at_100() -> None:
    """
    Pack many cars into a single segment to verify the score caps at 100.

    6 cars in s03 each with a close interval:
        6 × (20 + 15) = 210 → clamped to 100.0
    """
    cars = [
        CarSegmentState(segment_id="s03", interval_ahead_s=0.5)
        for _ in range(6)
    ]
    scores = compute_traffic_scores(cars, _SEGMENT_ORDER)

    assert scores.get("s03") == pytest.approx(100.0)


def test_scores_never_exceed_100_for_any_segment() -> None:
    """All computed scores must remain within [0, 100] for a large input."""
    # Saturate every segment with multiple cars.
    cars = [
        CarSegmentState(segment_id=seg, interval_ahead_s=0.3)
        for seg in _SEGMENT_ORDER
        for _ in range(10)
    ]
    scores = compute_traffic_scores(cars, _SEGMENT_ORDER)

    for seg, score in scores.items():
        assert 0.0 <= score <= 100.0, f"Score for {seg!r} out of bounds: {score}"
