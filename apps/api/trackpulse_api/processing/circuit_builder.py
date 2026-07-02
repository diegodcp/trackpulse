"""Pure circuit centerline extraction algorithm.

This module contains ONLY pure functions — no I/O, no DB, no HTTP.
Given raw car location samples, it produces a clean, segmented circuit polyline.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CircuitPoint:
    x: float
    y: float
    cumulative_dist: float


@dataclass(frozen=True)
class CircuitSegment:
    id: int
    start_idx: int
    end_idx: int
    sector: int  # 1, 2, or 3
    start_dist: float
    end_dist: float


@dataclass(frozen=True)
class CircuitGeometry:
    points: list[CircuitPoint]
    segments: list[CircuitSegment]
    bounds: dict  # {min_x, max_x, min_y, max_y}
    total_length: float
    source_driver: int
    source_lap: int


def deduplicate(coords: np.ndarray, threshold: float) -> np.ndarray:
    """Remove points that are within `threshold` meters of the previous kept point."""
    if len(coords) == 0:
        return coords
    mask = np.ones(len(coords), dtype=bool)
    last_kept = 0
    for i in range(1, len(coords)):
        dist = np.linalg.norm(coords[i] - coords[last_kept])
        if dist < threshold:
            mask[i] = False
        else:
            last_kept = i
    return coords[mask]


def smooth(coords: np.ndarray, window: int) -> np.ndarray:
    """Apply moving average smoothing. Window must be odd."""
    if window % 2 == 0:
        raise ValueError("Smoothing window must be odd")
    kernel = np.ones(window) / window
    x_smooth = np.convolve(coords[:, 0], kernel, mode="same")
    y_smooth = np.convolve(coords[:, 1], kernel, mode="same")
    return np.column_stack([x_smooth, y_smooth])


def interpolate_to_uniform(coords: np.ndarray, num_points: int) -> np.ndarray:
    """Resample polyline to num_points with equal arc-length spacing."""
    diffs = np.diff(coords, axis=0)
    segment_lengths = np.linalg.norm(diffs, axis=1)
    cumulative = np.concatenate([[0], np.cumsum(segment_lengths)])
    total_length = cumulative[-1]

    uniform_dists = np.linspace(0, total_length, num_points)

    x_interp = np.interp(uniform_dists, cumulative, coords[:, 0])
    y_interp = np.interp(uniform_dists, cumulative, coords[:, 1])

    return np.column_stack([x_interp, y_interp])


def compute_cumulative_distances(coords: np.ndarray) -> np.ndarray:
    """Return array of cumulative distances from start for each point."""
    diffs = np.diff(coords, axis=0)
    segment_lengths = np.linalg.norm(diffs, axis=1)
    return np.concatenate([[0], np.cumsum(segment_lengths)])


def divide_into_segments(
    num_points: int, total_length: float, num_segments: int
) -> list[CircuitSegment]:
    """Divide circuit into num_segments of equal arc-length."""
    segment_length = total_length / num_segments
    segments = []
    for i in range(num_segments):
        start_idx = int(i * num_points / num_segments)
        end_idx = int((i + 1) * num_points / num_segments) - 1
        sector = (i * 3) // num_segments + 1  # Map to sector 1/2/3
        segments.append(
            CircuitSegment(
                id=i,
                start_idx=start_idx,
                end_idx=end_idx,
                sector=sector,
                start_dist=i * segment_length,
                end_dist=(i + 1) * segment_length,
            )
        )
    return segments


def extract_circuit_centerline(
    raw_positions: list[dict],
    num_segments: int = 24,
    dedup_threshold_m: float = 3.0,
    smooth_window: int = 5,
    interpolation_points: int = 4000,
    source_driver: int = 0,
    source_lap: int = 0,
) -> CircuitGeometry:
    """Transform raw car location samples into a clean circuit centerline.

    Steps:
    1. Extract XY from raw positions (ordered by timestamp)
    2. Deduplicate: remove points within `dedup_threshold_m` of previous
    3. Smooth: apply `smooth_window`-point moving average
    4. Interpolate: resample to `interpolation_points` evenly-spaced points
    5. Compute cumulative distances
    6. Divide into `num_segments` of equal arc-length
    7. Compute bounding box

    Args:
        raw_positions: List of dicts with at minimum 'x' and 'y' keys,
                      ordered chronologically (one lap of data).
        num_segments: Number of segments to divide circuit into.
        dedup_threshold_m: Minimum distance between consecutive points.
        smooth_window: Moving average window size (must be odd).
        interpolation_points: Number of output centerline points.
        source_driver: Driver number used for the reference lap.
        source_lap: Lap number used for reference.

    Returns:
        CircuitGeometry with clean centerline, segments, and metadata.

    Raises:
        ValueError: If raw_positions has fewer than 50 points.
    """
    if len(raw_positions) < 50:
        raise ValueError(
            f"Need at least 50 raw points, got {len(raw_positions)} "
            f"(fewer than 50)"
        )

    # Step 1: Extract XY
    coords = np.array([[p["x"], p["y"]] for p in raw_positions])

    # Step 2: Deduplicate
    coords = deduplicate(coords, dedup_threshold_m)

    # Step 3: Smooth
    if len(coords) >= smooth_window:
        coords = smooth(coords, smooth_window)

    # Step 4: Interpolate to uniform spacing
    coords = interpolate_to_uniform(coords, interpolation_points)

    # Step 5: Compute cumulative distances
    cum_dists = compute_cumulative_distances(coords)
    total_length = float(cum_dists[-1])

    # Step 6: Divide into segments
    segments = divide_into_segments(interpolation_points, total_length, num_segments)

    # Step 7: Compute bounding box
    bounds = {
        "min_x": float(np.min(coords[:, 0])),
        "max_x": float(np.max(coords[:, 0])),
        "min_y": float(np.min(coords[:, 1])),
        "max_y": float(np.max(coords[:, 1])),
    }

    # Build CircuitPoint list
    points = [
        CircuitPoint(x=float(coords[i, 0]), y=float(coords[i, 1]), cumulative_dist=float(cum_dists[i]))
        for i in range(interpolation_points)
    ]

    return CircuitGeometry(
        points=points,
        segments=segments,
        bounds=bounds,
        total_length=total_length,
        source_driver=source_driver,
        source_lap=source_lap,
    )
