"""Largest Triangle Three Buckets (LTTB) downsampling algorithm.

Reduces large time-series datasets to a target number of points while
preserving the visual shape (peaks, valleys, trends). Used for chart
endpoints where pixel density is lower than data density.
"""

import numpy as np
from numpy.typing import NDArray


def lttb_downsample(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    target_points: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Downsample time-series data while preserving visual shape.

    Implements the Largest Triangle Three Buckets algorithm.
    Always keeps the first and last data points. For each interior bucket,
    selects the point that forms the largest triangle area with the
    previously selected point and the average of the next bucket.

    Args:
        x: Monotonically increasing time values (length n).
        y: Corresponding data values (length n).
        target_points: Desired output size (>= 3 for meaningful downsampling).

    Returns:
        Tuple of (x_downsampled, y_downsampled) with length == min(n, target_points).
    """
    n = len(x)
    if n <= target_points or target_points < 3:
        return x.copy(), y.copy()

    # Always keep first and last points
    bucket_size = (n - 2) / (target_points - 2)

    selected_indices = np.empty(target_points, dtype=np.intp)
    selected_indices[0] = 0
    prev_selected = 0

    for i in range(1, target_points - 1):
        # Current bucket boundaries
        bucket_start = int((i - 1) * bucket_size) + 1
        bucket_end = int(i * bucket_size) + 1
        bucket_end = min(bucket_end, n - 1)

        # Next bucket boundaries (for average point)
        next_start = int(i * bucket_size) + 1
        next_end = int((i + 1) * bucket_size) + 1
        next_end = min(next_end, n)

        # Average of next bucket
        avg_x = np.mean(x[next_start:next_end])
        avg_y = np.mean(y[next_start:next_end])

        # Find point in current bucket with max triangle area
        # Area = 0.5 * |x_a(y_b - y_c) + x_b(y_c - y_a) + x_c(y_a - y_b)|
        # Simplified since we only compare relative areas (skip 0.5 factor)
        x_a = x[prev_selected]
        y_a = y[prev_selected]

        # Vectorized area calculation for all points in bucket
        bucket_x = x[bucket_start:bucket_end]
        bucket_y = y[bucket_start:bucket_end]

        areas = np.abs(
            (x_a - avg_x) * (bucket_y - y_a)
            - (x_a - bucket_x) * (avg_y - y_a)
        )

        max_idx = bucket_start + int(np.argmax(areas))
        selected_indices[i] = max_idx
        prev_selected = max_idx

    selected_indices[-1] = n - 1

    return x[selected_indices], y[selected_indices]
