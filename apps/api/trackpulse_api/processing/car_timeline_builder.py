"""Pure car timeline builder — resamples raw position data into uniform-interval frames.

This module contains ONLY pure functions — no I/O, no DB, no HTTP.
Given raw car position samples and metadata, it produces a uniform-interval
timeline suitable for smooth frontend animation.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np


@dataclass(frozen=True)
class CarFrame:
    driver_number: int
    x: float
    y: float
    speed: int | None
    position: int | None
    lap_number: int | None
    name_acronym: str
    team_colour: str


@dataclass(frozen=True)
class TimelineFrame:
    timestamp: str  # ISO 8601
    elapsed_seconds: float  # Seconds from session start
    cars: list[CarFrame]


# Maximum gap (seconds) before we stop interpolating and treat it as a true absence
_MAX_GAP_SECONDS = 5.0


def interpolate_driver_positions(
    driver_positions: list[dict],
    grid_timestamps: list[datetime],
) -> list[tuple[float, float]]:
    """Linear interpolation of XY positions to grid timestamps.

    Returns list of (x, y) tuples aligned to grid_timestamps.
    NaN for timestamps outside the driver's data range.
    """
    if not driver_positions or not grid_timestamps:
        return [(np.nan, np.nan)] * len(grid_timestamps)

    origin = grid_timestamps[0]
    pos_times = np.array(
        [(p["timestamp"] - origin).total_seconds() for p in driver_positions]
    )
    pos_x = np.array([p["x"] for p in driver_positions], dtype=np.float64)
    pos_y = np.array([p["y"] for p in driver_positions], dtype=np.float64)
    grid_times = np.array(
        [(t - origin).total_seconds() for t in grid_timestamps]
    )

    # Interpolate with NaN outside data bounds
    x_interp = np.interp(grid_times, pos_times, pos_x, left=np.nan, right=np.nan)
    y_interp = np.interp(grid_times, pos_times, pos_y, left=np.nan, right=np.nan)

    # Null out points in large gaps (> _MAX_GAP_SECONDS between consecutive samples)
    if len(pos_times) > 1:
        for i, gt in enumerate(grid_times):
            if np.isnan(x_interp[i]):
                continue
            # Find surrounding sample indices
            idx = np.searchsorted(pos_times, gt)
            if idx == 0 or idx >= len(pos_times):
                continue
            gap = pos_times[idx] - pos_times[idx - 1]
            if gap > _MAX_GAP_SECONDS:
                # Only null if the grid point falls within the gap
                if pos_times[idx - 1] < gt < pos_times[idx]:
                    x_interp[i] = np.nan
                    y_interp[i] = np.nan

    return list(zip(x_interp.tolist(), y_interp.tolist()))


def _forward_fill_values(
    raw_data: list[dict],
    grid_timestamps: list[datetime],
    key: str,
) -> list:
    """Forward-fill a value from raw data to grid timestamps."""
    if not raw_data:
        return [None] * len(grid_timestamps)

    result = [None] * len(grid_timestamps)
    data_idx = 0
    current_value = None

    for i, gt in enumerate(grid_timestamps):
        # Advance data_idx to the latest sample at or before gt
        while data_idx < len(raw_data) and raw_data[data_idx]["timestamp"] <= gt:
            current_value = raw_data[data_idx].get(key)
            data_idx += 1
        result[i] = current_value

    return result


def build_car_timeline(
    raw_positions: list[dict],
    raw_telemetry: list[dict],
    raw_positions_data: list[dict],
    raw_laps: list[dict],
    drivers: list[dict],
    target_hz: float = 4.0,
    session_start: datetime | None = None,
) -> list[TimelineFrame]:
    """Resample raw position data into a uniform-interval timeline.

    Algorithm:
    1. Determine timeline bounds (first position timestamp → last)
    2. Create uniform timestamp grid at target_hz
    3. For each driver:
       a. Sort positions by timestamp
       b. Interpolate X, Y to each grid timestamp (np.interp)
       c. Forward-fill speed, position, lap_number from nearest prior sample
    4. Assemble frames: one per grid timestamp, containing all active drivers

    Args:
        raw_positions: Car XY positions [{driver_number, timestamp, x, y}]
        raw_telemetry: Car speed data [{driver_number, timestamp, speed}]
        raw_positions_data: Race positions [{driver_number, timestamp, position}]
        raw_laps: Lap boundaries [{driver_number, lap_number, date_start}]
        drivers: Driver metadata [{driver_number, name_acronym, team_colour}]
        target_hz: Output sample rate (default 4 Hz)
        session_start: Override session start timestamp

    Returns:
        List of TimelineFrame objects, one per time step
    """
    if not raw_positions:
        return []

    # Build driver lookup
    driver_map = {d["driver_number"]: d for d in drivers}
    driver_numbers = sorted(driver_map.keys())

    # Step 1: Determine bounds
    all_timestamps = sorted(set(p["timestamp"] for p in raw_positions))
    start_time = session_start or all_timestamps[0]
    end_time = all_timestamps[-1]
    duration_s = (end_time - start_time).total_seconds()

    if duration_s <= 0:
        return []

    num_frames = int(duration_s * target_hz)
    if num_frames == 0:
        return []

    # Step 2: Build uniform grid
    grid_timestamps = [
        start_time + timedelta(seconds=i / target_hz) for i in range(num_frames)
    ]

    # Step 3: Group data by driver
    positions_by_driver: dict[int, list[dict]] = {dn: [] for dn in driver_numbers}
    for p in raw_positions:
        dn = p["driver_number"]
        if dn in positions_by_driver:
            positions_by_driver[dn].append(p)

    telemetry_by_driver: dict[int, list[dict]] = {dn: [] for dn in driver_numbers}
    for t in raw_telemetry:
        dn = t["driver_number"]
        if dn in telemetry_by_driver:
            telemetry_by_driver[dn].append(t)

    race_pos_by_driver: dict[int, list[dict]] = {dn: [] for dn in driver_numbers}
    for p in raw_positions_data:
        dn = p["driver_number"]
        if dn in race_pos_by_driver:
            race_pos_by_driver[dn].append(p)

    laps_by_driver: dict[int, list[dict]] = {dn: [] for dn in driver_numbers}
    for lap in raw_laps:
        dn = lap["driver_number"]
        if dn in laps_by_driver:
            laps_by_driver[dn].append(lap)

    # Sort per-driver data by timestamp
    for dn in driver_numbers:
        positions_by_driver[dn].sort(key=lambda p: p["timestamp"])
        telemetry_by_driver[dn].sort(key=lambda t: t["timestamp"])
        race_pos_by_driver[dn].sort(key=lambda p: p["timestamp"])
        laps_by_driver[dn].sort(key=lambda l: l.get("date_start") or datetime.min.replace(tzinfo=timezone.utc))

    # Step 3b: Interpolate each driver
    driver_xy: dict[int, list[tuple[float, float]]] = {}
    driver_speed: dict[int, list] = {}
    driver_position: dict[int, list] = {}
    driver_lap: dict[int, list] = {}

    for dn in driver_numbers:
        driver_xy[dn] = interpolate_driver_positions(
            positions_by_driver[dn], grid_timestamps
        )
        driver_speed[dn] = _forward_fill_values(
            telemetry_by_driver[dn], grid_timestamps, "speed"
        )
        driver_position[dn] = _forward_fill_values(
            race_pos_by_driver[dn], grid_timestamps, "position"
        )
        driver_lap[dn] = _forward_fill_values(
            laps_by_driver[dn], grid_timestamps, "lap_number"
        )

    # Step 4: Assemble frames
    frames: list[TimelineFrame] = []
    for i, gt in enumerate(grid_timestamps):
        cars: list[CarFrame] = []
        for dn in driver_numbers:
            x, y = driver_xy[dn][i]
            # Skip drivers with no data at this timestamp (NaN = not active)
            if np.isnan(x) or np.isnan(y):
                continue

            meta = driver_map[dn]
            speed_val = driver_speed[dn][i]
            cars.append(CarFrame(
                driver_number=dn,
                x=round(x, 1),
                y=round(y, 1),
                speed=int(speed_val) if speed_val is not None else None,
                position=driver_position[dn][i],
                lap_number=driver_lap[dn][i],
                name_acronym=meta.get("name_acronym", ""),
                team_colour=meta.get("team_colour", "FFFFFF"),
            ))

        elapsed = (gt - start_time).total_seconds()
        frames.append(TimelineFrame(
            timestamp=gt.isoformat(),
            elapsed_seconds=round(elapsed, 3),
            cars=cars,
        ))

    return frames
