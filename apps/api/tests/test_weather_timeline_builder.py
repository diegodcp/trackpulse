"""Tests for weather_timeline_builder.py — pure function tests, no I/O."""

from datetime import datetime, timedelta, timezone

import pytest

from trackpulse_api.processing.weather_timeline_builder import (
    WeatherState,
    align_weather_to_timeline,
)

# Shared test constants
T0 = datetime(2024, 3, 2, 15, 0, 0, tzinfo=timezone.utc)


def _make_weather_sample(
    timestamp: datetime,
    air_temperature: float = 25.0,
    track_temperature: float = 40.0,
    humidity: float = 50.0,
    wind_speed: float = 3.0,
    wind_direction: int = 180,
    rainfall: bool = False,
) -> dict:
    """Helper to build a complete weather sample dict."""
    return {
        "timestamp": timestamp,
        "air_temperature": air_temperature,
        "track_temperature": track_temperature,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
        "rainfall": rainfall,
    }


class TestAlignWeatherToTimeline:
    def test_forward_fill_between_samples(self):
        """Grid timestamps between samples use the previous sample's values."""
        samples = [
            _make_weather_sample(T0, air_temperature=25.0),
            _make_weather_sample(T0 + timedelta(minutes=1), air_temperature=26.0),
        ]
        # Grid at 4Hz: 240 timestamps in 1 minute (before second sample arrives)
        grid = [T0 + timedelta(seconds=i / 4) for i in range(240)]

        result = align_weather_to_timeline(samples, grid)

        # All 240 frames should use first sample (none reach the 60s mark)
        assert result[0].air_temperature == 25.0
        assert result[100].air_temperature == 25.0
        assert result[239].air_temperature == 25.0

    def test_transitions_at_new_sample(self):
        """Weather state transitions when a new sample becomes the most recent."""
        samples = [
            _make_weather_sample(T0, air_temperature=25.0),
            _make_weather_sample(T0 + timedelta(minutes=1), air_temperature=27.0),
        ]
        grid = [
            T0 + timedelta(seconds=30),  # Before second sample
            T0 + timedelta(minutes=1),  # At second sample
            T0 + timedelta(minutes=1, seconds=30),  # After second sample
        ]

        result = align_weather_to_timeline(samples, grid)
        assert result[0].air_temperature == 25.0  # Uses first sample
        assert result[1].air_temperature == 27.0  # Transitions to second
        assert result[2].air_temperature == 27.0  # Stays at second

    def test_rainfall_boolean(self):
        """Rainfall is properly converted to boolean."""
        samples = [
            _make_weather_sample(T0, rainfall=False),
            _make_weather_sample(T0 + timedelta(minutes=5), rainfall=True),
        ]
        grid = [T0, T0 + timedelta(minutes=5)]

        result = align_weather_to_timeline(samples, grid)
        assert result[0].rainfall is False
        assert result[1].rainfall is True

    def test_rainfall_from_integer(self):
        """Rainfall integer values (0/1 from DB) are properly coerced to boolean."""
        samples = [
            {
                "timestamp": T0,
                "air_temperature": 25.0,
                "track_temperature": 40.0,
                "humidity": 50.0,
                "wind_speed": 3.0,
                "wind_direction": 180,
                "rainfall": 0,
            },
            {
                "timestamp": T0 + timedelta(minutes=5),
                "air_temperature": 25.0,
                "track_temperature": 40.0,
                "humidity": 50.0,
                "wind_speed": 3.0,
                "wind_direction": 180,
                "rainfall": 1,
            },
        ]
        grid = [T0, T0 + timedelta(minutes=5)]

        result = align_weather_to_timeline(samples, grid)
        assert result[0].rainfall is False
        assert result[1].rainfall is True

    def test_empty_samples_raises(self):
        """Raises ValueError with no weather data."""
        with pytest.raises(ValueError, match="No weather samples"):
            align_weather_to_timeline([], [T0])

    def test_single_sample_fills_all(self):
        """A single sample forward-fills the entire timeline."""
        samples = [_make_weather_sample(T0, air_temperature=30.0)]
        grid = [T0 + timedelta(seconds=i) for i in range(100)]

        result = align_weather_to_timeline(samples, grid)
        assert all(w.air_temperature == 30.0 for w in result)

    def test_output_length_matches_grid(self):
        """Output has exactly as many entries as grid timestamps."""
        samples = [_make_weather_sample(T0)]
        grid = [T0 + timedelta(seconds=i) for i in range(500)]

        result = align_weather_to_timeline(samples, grid)
        assert len(result) == 500

    def test_wind_direction_preserved(self):
        """Wind direction is an integer 0-359, preserved exactly."""
        samples = [_make_weather_sample(T0, wind_direction=359)]
        grid = [T0]

        result = align_weather_to_timeline(samples, grid)
        assert result[0].wind_direction == 359

    def test_wind_direction_is_int(self):
        """Wind direction is returned as int even if input is float-like."""
        samples = [
            {
                "timestamp": T0,
                "air_temperature": 25.0,
                "track_temperature": 40.0,
                "humidity": 50.0,
                "wind_speed": 3.0,
                "wind_direction": 270.0,  # float from DB
                "rainfall": False,
            }
        ]
        grid = [T0]

        result = align_weather_to_timeline(samples, grid)
        assert result[0].wind_direction == 270
        assert isinstance(result[0].wind_direction, int)

    def test_unsorted_samples_are_sorted(self):
        """Samples provided out of order are sorted by timestamp."""
        samples = [
            _make_weather_sample(T0 + timedelta(minutes=2), air_temperature=28.0),
            _make_weather_sample(T0, air_temperature=24.0),
            _make_weather_sample(T0 + timedelta(minutes=1), air_temperature=26.0),
        ]
        grid = [
            T0 + timedelta(seconds=30),
            T0 + timedelta(minutes=1, seconds=30),
            T0 + timedelta(minutes=2, seconds=30),
        ]

        result = align_weather_to_timeline(samples, grid)
        assert result[0].air_temperature == 24.0  # First sample
        assert result[1].air_temperature == 26.0  # Second sample
        assert result[2].air_temperature == 28.0  # Third sample

    def test_grid_before_first_sample_uses_first(self):
        """Grid timestamps before the first sample use the first sample's values."""
        samples = [
            _make_weather_sample(T0 + timedelta(minutes=5), air_temperature=30.0),
        ]
        # Grid starts before the first weather sample
        grid = [T0, T0 + timedelta(minutes=2), T0 + timedelta(minutes=5)]

        result = align_weather_to_timeline(samples, grid)
        # All should use the only available sample (forward-fill from idx 0)
        assert result[0].air_temperature == 30.0
        assert result[1].air_temperature == 30.0
        assert result[2].air_temperature == 30.0

    def test_returns_frozen_dataclass(self):
        """Output items are frozen WeatherState dataclass instances."""
        samples = [_make_weather_sample(T0)]
        grid = [T0]

        result = align_weather_to_timeline(samples, grid)
        assert isinstance(result[0], WeatherState)

        with pytest.raises(Exception):  # FrozenInstanceError
            result[0].air_temperature = 99.0  # type: ignore[misc]

    def test_multiple_fields_consistent(self):
        """All fields from a sample are consistently forwarded to the same frame."""
        samples = [
            _make_weather_sample(
                T0,
                air_temperature=22.0,
                track_temperature=38.0,
                humidity=65.0,
                wind_speed=5.5,
                wind_direction=45,
                rainfall=True,
            ),
        ]
        grid = [T0 + timedelta(seconds=10)]

        result = align_weather_to_timeline(samples, grid)
        w = result[0]
        assert w.air_temperature == 22.0
        assert w.track_temperature == 38.0
        assert w.humidity == 65.0
        assert w.wind_speed == 5.5
        assert w.wind_direction == 45
        assert w.rainfall is True
