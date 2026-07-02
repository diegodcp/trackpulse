"""Tests for car_timeline_builder.py — pure function tests, no I/O."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from trackpulse_api.processing.car_timeline_builder import (
    CarFrame,
    TimelineFrame,
    build_car_timeline,
    interpolate_driver_positions,
)

# Shared test constants
T0 = datetime(2024, 3, 2, 15, 0, 0, tzinfo=timezone.utc)


def _make_positions(
    driver_numbers: list[int],
    duration_s: float = 10.0,
    sample_hz: float = 3.7,
    start_time: datetime = T0,
) -> list[dict]:
    """Generate synthetic position data for testing."""
    positions = []
    num_samples = int(duration_s * sample_hz)
    for dn in driver_numbers:
        for i in range(num_samples):
            ts = start_time + timedelta(seconds=i / sample_hz)
            # Circular track simulation
            angle = (i / num_samples) * 2 * 3.14159 + dn * 0.1
            positions.append({
                "driver_number": dn,
                "timestamp": ts,
                "x": 100.0 * np.cos(angle) + dn * 10,
                "y": 100.0 * np.sin(angle) + dn * 5,
            })
    return positions


def _make_drivers(driver_numbers: list[int]) -> list[dict]:
    """Generate driver metadata for testing."""
    names = {1: "VER", 16: "LEC", 44: "HAM", 4: "NOR", 11: "PER"}
    colours = {1: "3671C6", 16: "E80020", 44: "27F4D2", 4: "FF8000", 11: "3671C6"}
    return [
        {
            "driver_number": dn,
            "name_acronym": names.get(dn, f"D{dn:02d}"),
            "team_colour": colours.get(dn, "FFFFFF"),
        }
        for dn in driver_numbers
    ]


class TestInterpolateDriverPositions:
    def test_exact_timestamps_match(self):
        """When grid aligns with data timestamps, values are exact."""
        positions = [
            {"timestamp": T0, "x": 0.0, "y": 0.0},
            {"timestamp": T0 + timedelta(seconds=1), "x": 10.0, "y": 5.0},
        ]
        grid = [T0, T0 + timedelta(seconds=1)]
        result = interpolate_driver_positions(positions, grid)
        assert result[0] == (0.0, 0.0)
        assert result[1] == (10.0, 5.0)

    def test_midpoint_interpolation(self):
        """Midpoint between two samples is linearly interpolated."""
        positions = [
            {"timestamp": T0, "x": 0.0, "y": 0.0},
            {"timestamp": T0 + timedelta(seconds=2), "x": 10.0, "y": 10.0},
        ]
        grid = [T0, T0 + timedelta(seconds=1), T0 + timedelta(seconds=2)]
        result = interpolate_driver_positions(positions, grid)
        assert abs(result[1][0] - 5.0) < 0.01
        assert abs(result[1][1] - 5.0) < 0.01

    def test_nan_before_first_position(self):
        """Grid timestamps before first data point return NaN."""
        positions = [
            {"timestamp": T0 + timedelta(seconds=5), "x": 10.0, "y": 10.0},
        ]
        grid = [T0, T0 + timedelta(seconds=5)]
        result = interpolate_driver_positions(positions, grid)
        assert np.isnan(result[0][0])
        assert np.isnan(result[0][1])

    def test_nan_after_last_position(self):
        """Grid timestamps after last data point return NaN (DNF handling)."""
        positions = [
            {"timestamp": T0, "x": 0.0, "y": 0.0},
            {"timestamp": T0 + timedelta(seconds=10), "x": 50.0, "y": 50.0},
        ]
        grid = [T0 + timedelta(seconds=15)]
        result = interpolate_driver_positions(positions, grid)
        assert np.isnan(result[0][0])
        assert np.isnan(result[0][1])

    def test_empty_positions_returns_nan(self):
        """Empty position list returns all NaN."""
        grid = [T0, T0 + timedelta(seconds=1)]
        result = interpolate_driver_positions([], grid)
        assert all(np.isnan(x) and np.isnan(y) for x, y in result)

    def test_empty_grid_returns_empty(self):
        """Empty grid returns empty list."""
        positions = [{"timestamp": T0, "x": 0.0, "y": 0.0}]
        result = interpolate_driver_positions(positions, [])
        assert result == []

    def test_large_gap_nulled_out(self):
        """Interpolation through gaps > 5s produces NaN (avoid teleportation)."""
        positions = [
            {"timestamp": T0, "x": 0.0, "y": 0.0},
            {"timestamp": T0 + timedelta(seconds=10), "x": 100.0, "y": 100.0},
        ]
        # Grid point at 5s — within the >5s gap
        grid = [T0 + timedelta(seconds=5)]
        result = interpolate_driver_positions(positions, grid)
        assert np.isnan(result[0][0])
        assert np.isnan(result[0][1])

    def test_small_gap_interpolated(self):
        """Gaps <= 5s are interpolated normally."""
        positions = [
            {"timestamp": T0, "x": 0.0, "y": 0.0},
            {"timestamp": T0 + timedelta(seconds=4), "x": 40.0, "y": 40.0},
        ]
        grid = [T0 + timedelta(seconds=2)]
        result = interpolate_driver_positions(positions, grid)
        assert abs(result[0][0] - 20.0) < 0.01
        assert abs(result[0][1] - 20.0) < 0.01


class TestBuildCarTimeline:
    def test_frame_count_matches_duration(self):
        """Number of frames = int(duration * hz)."""
        drivers = [1, 16]
        positions = _make_positions(drivers, duration_s=10.0)
        timeline = build_car_timeline(
            raw_positions=positions,
            raw_telemetry=[],
            raw_positions_data=[],
            raw_laps=[],
            drivers=_make_drivers(drivers),
            target_hz=4.0,
        )
        # Actual data spans ~9.73s (37 samples at 3.7Hz), int(9.73*4) = 38
        num_samples = int(10.0 * 3.7)
        actual_duration = (num_samples - 1) / 3.7
        expected_frames = int(actual_duration * 4.0)
        assert len(timeline) == expected_frames

    def test_all_drivers_present_in_frame(self):
        """Each frame contains entries for all active drivers."""
        drivers = [1, 16, 44]
        positions = _make_positions(drivers, duration_s=5.0)
        timeline = build_car_timeline(
            raw_positions=positions,
            raw_telemetry=[],
            raw_positions_data=[],
            raw_laps=[],
            drivers=_make_drivers(drivers),
            target_hz=4.0,
        )
        # First frame should have all 3 drivers
        assert len(timeline[0].cars) == 3

    def test_driver_metadata_attached(self):
        """Car frames include name_acronym and team_colour."""
        drivers = [16]
        positions = _make_positions(drivers, duration_s=5.0)
        timeline = build_car_timeline(
            raw_positions=positions,
            raw_telemetry=[],
            raw_positions_data=[],
            raw_laps=[],
            drivers=[
                {"driver_number": 16, "name_acronym": "LEC", "team_colour": "E80020"}
            ],
            target_hz=4.0,
        )
        lec = next(c for c in timeline[0].cars if c.driver_number == 16)
        assert lec.name_acronym == "LEC"
        assert lec.team_colour == "E80020"

    def test_elapsed_seconds_monotonic(self):
        """elapsed_seconds increases monotonically across frames."""
        drivers = [1]
        positions = _make_positions(drivers, duration_s=5.0)
        timeline = build_car_timeline(
            raw_positions=positions,
            raw_telemetry=[],
            raw_positions_data=[],
            raw_laps=[],
            drivers=_make_drivers(drivers),
            target_hz=4.0,
        )
        elapsed = [f.elapsed_seconds for f in timeline]
        assert elapsed == sorted(elapsed)
        assert all(elapsed[i] < elapsed[i + 1] for i in range(len(elapsed) - 1))

    def test_speed_forward_filled(self):
        """Speed from telemetry is forward-filled to grid timestamps."""
        drivers = [1]
        positions = _make_positions(drivers, duration_s=5.0)
        telemetry = [
            {"driver_number": 1, "timestamp": T0, "speed": 200},
            {"driver_number": 1, "timestamp": T0 + timedelta(seconds=3), "speed": 250},
        ]
        timeline = build_car_timeline(
            raw_positions=positions,
            raw_telemetry=telemetry,
            raw_positions_data=[],
            raw_laps=[],
            drivers=_make_drivers(drivers),
            target_hz=4.0,
        )
        # First frame should have speed 200
        car = next(c for c in timeline[0].cars if c.driver_number == 1)
        assert car.speed == 200
        # Frame at 3s (index 12) should have speed 250
        car_at_3s = next(c for c in timeline[12].cars if c.driver_number == 1)
        assert car_at_3s.speed == 250

    def test_position_forward_filled(self):
        """Race position is forward-filled."""
        drivers = [1]
        positions = _make_positions(drivers, duration_s=5.0)
        race_positions = [
            {"driver_number": 1, "timestamp": T0, "position": 3},
            {"driver_number": 1, "timestamp": T0 + timedelta(seconds=2), "position": 2},
        ]
        timeline = build_car_timeline(
            raw_positions=positions,
            raw_telemetry=[],
            raw_positions_data=race_positions,
            raw_laps=[],
            drivers=_make_drivers(drivers),
            target_hz=4.0,
        )
        car_first = next(c for c in timeline[0].cars if c.driver_number == 1)
        assert car_first.position == 3
        car_at_2s = next(c for c in timeline[8].cars if c.driver_number == 1)
        assert car_at_2s.position == 2

    def test_empty_positions_returns_empty(self):
        """No raw positions → empty timeline."""
        timeline = build_car_timeline(
            raw_positions=[],
            raw_telemetry=[],
            raw_positions_data=[],
            raw_laps=[],
            drivers=_make_drivers([1]),
            target_hz=4.0,
        )
        assert timeline == []

    def test_dnf_driver_disappears(self):
        """A driver who stops reporting data disappears from later frames."""
        # Driver 1 has full data, driver 16 stops at t=3s
        positions_d1 = _make_positions([1], duration_s=10.0)
        positions_d16 = _make_positions([16], duration_s=3.0)

        timeline = build_car_timeline(
            raw_positions=positions_d1 + positions_d16,
            raw_telemetry=[],
            raw_positions_data=[],
            raw_laps=[],
            drivers=_make_drivers([1, 16]),
            target_hz=4.0,
        )

        # Last frame should only have driver 1 (driver 16 DNF'd)
        last_frame = timeline[-1]
        driver_numbers = [c.driver_number for c in last_frame.cars]
        assert 1 in driver_numbers
        assert 16 not in driver_numbers

    def test_custom_target_hz(self):
        """Different target_hz produces different frame count."""
        drivers = [1]
        positions = _make_positions(drivers, duration_s=10.0)
        timeline_2hz = build_car_timeline(
            raw_positions=positions,
            raw_telemetry=[],
            raw_positions_data=[],
            raw_laps=[],
            drivers=_make_drivers(drivers),
            target_hz=2.0,
        )
        timeline_4hz = build_car_timeline(
            raw_positions=positions,
            raw_telemetry=[],
            raw_positions_data=[],
            raw_laps=[],
            drivers=_make_drivers(drivers),
            target_hz=4.0,
        )
        # 4Hz should produce ~2x as many frames as 2Hz
        assert len(timeline_4hz) == len(timeline_2hz) * 2

    def test_coordinates_rounded(self):
        """Output coordinates are rounded to 1 decimal place."""
        drivers = [1]
        positions = [
            {"driver_number": 1, "timestamp": T0, "x": 1.23456, "y": 7.89012},
            {"driver_number": 1, "timestamp": T0 + timedelta(seconds=2), "x": 5.67890, "y": 3.45678},
        ]
        timeline = build_car_timeline(
            raw_positions=positions,
            raw_telemetry=[],
            raw_positions_data=[],
            raw_laps=[],
            drivers=_make_drivers(drivers),
            target_hz=1.0,
        )
        car = timeline[0].cars[0]
        assert car.x == 1.2
        assert car.y == 7.9
