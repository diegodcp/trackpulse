"""Tests for wind_derivation.py — pure function tests, no I/O."""

import pytest

from trackpulse_api.processing.wind_derivation import (
    SegmentWind,
    WindClass,
    angle_difference,
    compute_track_heading,
    derive_segment_wind,
)


class TestAngleDifference:
    def test_same_angle(self):
        assert angle_difference(90, 90) == 0

    def test_small_positive(self):
        assert angle_difference(95, 90) == 5

    def test_small_negative(self):
        assert angle_difference(85, 90) == -5

    def test_wrap_around_positive(self):
        """1° from 359° is +2° difference, not -358°."""
        result = angle_difference(1, 359)
        assert result == pytest.approx(2, abs=0.01)

    def test_wrap_around_negative(self):
        """359° from 1° is -2° difference, not +358°."""
        result = angle_difference(359, 1)
        assert result == pytest.approx(-2, abs=0.01)

    def test_opposite(self):
        assert abs(angle_difference(0, 180)) == 180

    def test_quarter_turn(self):
        assert angle_difference(90, 0) == 90

    def test_negative_quarter_turn(self):
        assert angle_difference(0, 90) == -90

    def test_large_wrap(self):
        """350° from 10° should be -20°."""
        assert angle_difference(350, 10) == pytest.approx(-20, abs=0.01)


class TestComputeTrackHeading:
    def test_straight_east(self):
        """Track going east (increasing X) = 90° heading."""
        points = [{"x": i * 10, "y": 0} for i in range(20)]
        heading = compute_track_heading(points, idx=5)
        assert heading == pytest.approx(90, abs=1)

    def test_straight_north(self):
        """Track going north (increasing Y) = 0° heading."""
        points = [{"x": 0, "y": i * 10} for i in range(20)]
        heading = compute_track_heading(points, idx=5)
        assert heading == pytest.approx(0, abs=1)

    def test_straight_south(self):
        """Track going south (decreasing Y) = 180° heading."""
        points = [{"x": 0, "y": -i * 10} for i in range(20)]
        heading = compute_track_heading(points, idx=5)
        assert heading == pytest.approx(180, abs=1)

    def test_straight_west(self):
        """Track going west (decreasing X) = 270° heading."""
        points = [{"x": -i * 10, "y": 0} for i in range(20)]
        heading = compute_track_heading(points, idx=5)
        assert heading == pytest.approx(270, abs=1)

    def test_diagonal_northeast(self):
        """Track going northeast = 45° heading."""
        points = [{"x": i * 10, "y": i * 10} for i in range(20)]
        heading = compute_track_heading(points, idx=5)
        assert heading == pytest.approx(45, abs=1)

    def test_end_of_track_uses_backward(self):
        """At the last point, should still compute a valid heading."""
        points = [{"x": i * 10, "y": 0} for i in range(20)]
        heading = compute_track_heading(points, idx=19)
        assert heading == pytest.approx(90, abs=1)


class TestDeriveSegmentWind:
    def test_pure_headwind(self):
        """Wind from same direction as track heading → headwind."""
        # Track goes North (0°), wind from North (0°) → headwind
        points = [{"x": 0, "y": i * 10} for i in range(100)]
        segments = [{"id": 0, "start_idx": 0, "end_idx": 99}]
        result = derive_segment_wind(5.0, 0, points, segments)
        assert result[0].wind_class == WindClass.HEADWIND
        assert result[0].headwind_component > 0
        assert result[0].effective_speed == pytest.approx(5.0, abs=0.1)

    def test_pure_tailwind(self):
        """Wind from opposite direction → tailwind."""
        # Track goes North (0°), wind from South (180°) → tailwind
        points = [{"x": 0, "y": i * 10} for i in range(100)]
        segments = [{"id": 0, "start_idx": 0, "end_idx": 99}]
        result = derive_segment_wind(5.0, 180, points, segments)
        assert result[0].wind_class == WindClass.TAILWIND
        assert result[0].headwind_component < 0

    def test_pure_crosswind_from_east(self):
        """Wind from East (90°) on northbound track → crosswind right."""
        points = [{"x": 0, "y": i * 10} for i in range(100)]
        segments = [{"id": 0, "start_idx": 0, "end_idx": 99}]
        result = derive_segment_wind(5.0, 90, points, segments)
        assert result[0].wind_class == WindClass.CROSSWIND_RIGHT
        assert result[0].crosswind_component > 0

    def test_pure_crosswind_from_west(self):
        """Wind from West (270°) on northbound track → crosswind left."""
        points = [{"x": 0, "y": i * 10} for i in range(100)]
        segments = [{"id": 0, "start_idx": 0, "end_idx": 99}]
        result = derive_segment_wind(5.0, 270, points, segments)
        assert result[0].wind_class == WindClass.CROSSWIND_LEFT
        assert result[0].crosswind_component < 0

    def test_zero_wind_speed(self):
        """Zero wind → all components are zero."""
        points = [{"x": 0, "y": i * 10} for i in range(100)]
        segments = [{"id": 0, "start_idx": 0, "end_idx": 99}]
        result = derive_segment_wind(0.0, 90, points, segments)
        assert result[0].effective_speed == 0.0
        assert result[0].headwind_component == 0.0
        assert result[0].crosswind_component == 0.0

    def test_multiple_segments_different_headings(self):
        """Circuit with curves → different segments get different wind classes."""
        # L-shaped track: first half goes East, second half goes North
        points_east = [{"x": i * 10, "y": 0} for i in range(50)]
        points_north = [{"x": 500, "y": i * 10} for i in range(50)]
        points = points_east + points_north
        segments = [
            {"id": 0, "start_idx": 0, "end_idx": 49},
            {"id": 1, "start_idx": 50, "end_idx": 99},
        ]
        # Wind from East (90°):
        # Segment 0 (heading East/90°) → headwind (wind from same direction as travel)
        # Segment 1 (heading North/0°) → crosswind from right
        result = derive_segment_wind(5.0, 90, points, segments)
        assert result[0].wind_class == WindClass.HEADWIND
        assert result[1].wind_class == WindClass.CROSSWIND_RIGHT

    def test_segment_id_preserved(self):
        """Each result carries the correct segment_id."""
        points = [{"x": 0, "y": i * 10} for i in range(100)]
        segments = [
            {"id": 7, "start_idx": 0, "end_idx": 49},
            {"id": 12, "start_idx": 50, "end_idx": 99},
        ]
        result = derive_segment_wind(3.0, 45, points, segments)
        assert result[0].segment_id == 7
        assert result[1].segment_id == 12

    def test_borderline_45_degree_is_headwind(self):
        """Exactly 45° from head-on is still classified as headwind."""
        # Track goes North (0°), wind from NE (45°) → border case = headwind
        points = [{"x": 0, "y": i * 10} for i in range(100)]
        segments = [{"id": 0, "start_idx": 0, "end_idx": 99}]
        result = derive_segment_wind(5.0, 45, points, segments)
        assert result[0].wind_class == WindClass.HEADWIND

    def test_borderline_135_degree_is_tailwind(self):
        """Exactly 135° from head-on is classified as tailwind."""
        # Track goes North (0°), wind from SE (135°) → border = tailwind
        points = [{"x": 0, "y": i * 10} for i in range(100)]
        segments = [{"id": 0, "start_idx": 0, "end_idx": 99}]
        result = derive_segment_wind(5.0, 135, points, segments)
        assert result[0].wind_class == WindClass.TAILWIND

    def test_returns_list_same_length_as_segments(self):
        """Output length matches the number of segments."""
        points = [{"x": 0, "y": i * 10} for i in range(200)]
        segments = [
            {"id": i, "start_idx": i * 50, "end_idx": (i + 1) * 50 - 1}
            for i in range(4)
        ]
        result = derive_segment_wind(4.0, 270, points, segments)
        assert len(result) == 4

    def test_strong_wind_effective_speed(self):
        """Strong pure headwind: effective_speed ≈ wind_speed."""
        points = [{"x": 0, "y": i * 10} for i in range(100)]
        segments = [{"id": 0, "start_idx": 0, "end_idx": 99}]
        result = derive_segment_wind(12.0, 0, points, segments)
        assert result[0].effective_speed == pytest.approx(12.0, abs=0.1)

    def test_relative_angle_sign_convention(self):
        """Positive relative angle = wind from right of car's travel direction."""
        # Track goes North (0°), wind from East (90°)
        # Relative should be positive (wind from right)
        points = [{"x": 0, "y": i * 10} for i in range(100)]
        segments = [{"id": 0, "start_idx": 0, "end_idx": 99}]
        result = derive_segment_wind(5.0, 90, points, segments)
        assert result[0].relative_angle > 0

        # Wind from West (270°) → negative (wind from left)
        result2 = derive_segment_wind(5.0, 270, points, segments)
        assert result2[0].relative_angle < 0
