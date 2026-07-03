"""Pure weather timeline builder — aligns weather samples to a timeline grid.

This module contains ONLY pure functions — no I/O, no DB, no HTTP.
Given raw weather samples and a target timestamp grid, it produces a
forward-filled weather timeline suitable for merging into car timeline frames.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class WeatherState:
    air_temperature: float  # °C
    track_temperature: float  # °C
    humidity: float  # %
    wind_speed: float  # m/s
    wind_direction: int  # 0-359 degrees
    rainfall: bool


def align_weather_to_timeline(
    weather_samples: list[dict],
    grid_timestamps: list[datetime],
) -> list[WeatherState]:
    """Align weather samples (≈1/min) to timeline grid (e.g. 4Hz) using forward-fill.

    Strategy:
    - Weather doesn't change significantly between samples (1-minute intervals)
    - For each grid timestamp, use the most recent weather sample (forward-fill)
    - Do NOT interpolate continuous values — the measurement IS the state
      until the next measurement arrives

    Args:
        weather_samples: Chronologically sorted weather measurements.
            Each dict must have keys: timestamp, air_temperature,
            track_temperature, humidity, wind_speed, wind_direction, rainfall.
        grid_timestamps: Target timestamps to align to (from car timeline).

    Returns:
        List of WeatherState, one per grid timestamp (same length as grid_timestamps).

    Raises:
        ValueError: If weather_samples is empty.
    """
    if not weather_samples:
        raise ValueError("No weather samples available")

    sorted_samples = sorted(weather_samples, key=lambda w: w["timestamp"])

    result: list[WeatherState] = []
    sample_idx = 0

    for ts in grid_timestamps:
        # Advance to the latest sample that is <= ts
        while (
            sample_idx < len(sorted_samples) - 1
            and sorted_samples[sample_idx + 1]["timestamp"] <= ts
        ):
            sample_idx += 1

        sample = sorted_samples[sample_idx]
        result.append(
            WeatherState(
                air_temperature=sample["air_temperature"],
                track_temperature=sample["track_temperature"],
                humidity=sample["humidity"],
                wind_speed=sample["wind_speed"],
                wind_direction=int(sample["wind_direction"]),
                rainfall=bool(sample["rainfall"]),
            )
        )

    return result
