"""Unit tests for the pure circuit_builder extraction algorithm."""

import numpy as np
import pytest

from trackpulse_api.processing.circuit_builder import (
    CircuitGeometry,
    deduplicate,
    divide_into_segments,
    extract_circuit_centerline,
    interpolate_to_uniform,
    smooth,
)


class TestDeduplicate:
    def test_removes_duplicate_points(self):
        """Points within threshold are removed."""
        coords = np.array([[0, 0], [1, 0], [1.5, 0], [5, 0], [5.1, 0], [10, 0]], dtype=float)
        result = deduplicate(coords, threshold=3.0)
        # Points too close to the previously kept point get removed
        assert len(result) < len(coords)

    def test_preserves_well_spaced_points(self):
        """Points beyond threshold are all kept."""
        coords = np.array([[0, 0], [5, 0], [10, 0], [15, 0]], dtype=float)
        result = deduplicate(coords, threshold=3.0)
        assert len(result) == 4

    def test_always_keeps_first_point(self):
        """First point is never removed."""
        coords = np.array([[0, 0], [0.1, 0]], dtype=float)
        result = deduplicate(coords, threshold=3.0)
        assert result[0][0] == 0.0
        assert len(result) == 1  # Second point removed (within threshold)

    def test_empty_input(self):
        """Empty array returns empty array."""
        coords = np.array([], dtype=float).reshape(0, 2)
        result = deduplicate(coords, threshold=3.0)
        assert len(result) == 0

    def test_measures_from_last_kept_point(self):
        """Distance is measured from last kept point, not previous point."""
        # Points: 0, 2, 4 — each is 2m from the previous, all within 3m of previous
        # But 4 is 4m from 0 (the first kept point), so it should be kept
        coords = np.array([[0, 0], [2, 0], [4, 0], [6, 0]], dtype=float)
        result = deduplicate(coords, threshold=3.0)
        # 0 kept, 2 removed (2m from 0 < 3), 4 kept (4m from 0 >= 3), 6 removed (2m from 4 < 3)
        assert len(result) == 2
        np.testing.assert_array_equal(result[0], [0, 0])
        np.testing.assert_array_equal(result[1], [4, 0])


class TestSmooth:
    def test_straight_line_unchanged(self):
        """Smoothing a straight line produces the same line (center region)."""
        coords = np.array([[i, 0.0] for i in range(20)])
        result = smooth(coords, window=5)
        # Central points should be unchanged for a straight line
        np.testing.assert_allclose(result[5:15, 1], 0, atol=1e-10)
        np.testing.assert_allclose(result[5:15, 0], np.arange(5, 15), atol=1e-10)

    def test_reduces_noise(self):
        """Smoothing reduces oscillation amplitude."""
        x = np.arange(100, dtype=float)
        y = np.sin(x * 0.5) * 10
        coords = np.column_stack([x, y])
        result = smooth(coords, window=5)
        # Max amplitude should be reduced
        assert np.max(np.abs(result[10:90, 1])) < np.max(np.abs(y))

    def test_rejects_even_window(self):
        """Even window size raises ValueError."""
        coords = np.array([[i, 0.0] for i in range(20)])
        with pytest.raises(ValueError, match="odd"):
            smooth(coords, window=4)


class TestInterpolate:
    def test_output_length(self):
        """Interpolation produces exactly num_points output."""
        coords = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
        result = interpolate_to_uniform(coords, num_points=100)
        assert len(result) == 100

    def test_preserves_start_end(self):
        """First and last points match original."""
        coords = np.array([[0, 0], [10, 0], [10, 10]], dtype=float)
        result = interpolate_to_uniform(coords, num_points=50)
        np.testing.assert_allclose(result[0], [0, 0], atol=1e-6)
        np.testing.assert_allclose(result[-1], [10, 10], atol=1e-6)

    def test_uniform_spacing(self):
        """Output points are approximately uniformly spaced."""
        coords = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
        result = interpolate_to_uniform(coords, num_points=100)
        dists = np.linalg.norm(np.diff(result, axis=0), axis=1)
        # All inter-point distances should be approximately equal
        assert np.std(dists) / np.mean(dists) < 0.01


class TestDivideSegments:
    def test_correct_segment_count(self):
        """Produces exactly num_segments segments."""
        segments = divide_into_segments(4000, 5000.0, 24)
        assert len(segments) == 24

    def test_segments_cover_full_circuit(self):
        """Segments span from index 0 to last point."""
        segments = divide_into_segments(4000, 5000.0, 24)
        assert segments[0].start_idx == 0
        assert segments[-1].end_idx == 3999

    def test_sector_assignment(self):
        """First 8 segments are sector 1, next 8 sector 2, last 8 sector 3."""
        segments = divide_into_segments(4000, 5000.0, 24)
        assert all(s.sector == 1 for s in segments[:8])
        assert all(s.sector == 2 for s in segments[8:16])
        assert all(s.sector == 3 for s in segments[16:])

    def test_segment_distances(self):
        """Segment start/end distances cover the total length."""
        segments = divide_into_segments(4000, 5000.0, 24)
        assert segments[0].start_dist == pytest.approx(0.0)
        assert segments[-1].end_dist == pytest.approx(5000.0)

    def test_no_index_gaps(self):
        """No point indices are missed between segments."""
        segments = divide_into_segments(4000, 5000.0, 24)
        for i in range(len(segments) - 1):
            # end_idx of one segment + 1 == start_idx of next
            assert segments[i].end_idx + 1 == segments[i + 1].start_idx


class TestExtractCircuitCenterline:
    def test_full_pipeline_with_oval(self):
        """Full extraction on a simple oval produces valid geometry."""
        t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
        raw = [{"x": float(100 * np.cos(a)), "y": float(50 * np.sin(a))} for a in t]

        result = extract_circuit_centerline(raw, num_segments=12)

        assert len(result.points) == 4000
        assert len(result.segments) == 12
        assert result.total_length > 0
        assert result.bounds["min_x"] < result.bounds["max_x"]
        assert result.bounds["min_y"] < result.bounds["max_y"]

    def test_rejects_too_few_points(self):
        """Raises ValueError if fewer than 50 raw points."""
        raw = [{"x": float(i), "y": 0.0} for i in range(30)]
        with pytest.raises(ValueError, match="fewer than 50"):
            extract_circuit_centerline(raw)

    def test_deterministic(self):
        """Same input always produces same output."""
        t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
        raw = [{"x": float(100 * np.cos(a)), "y": float(50 * np.sin(a))} for a in t]

        result1 = extract_circuit_centerline(raw)
        result2 = extract_circuit_centerline(raw)

        assert result1.total_length == result2.total_length
        assert result1.points[100].x == result2.points[100].x
        assert result1.points[100].y == result2.points[100].y

    def test_custom_parameters(self):
        """Custom parameters are respected."""
        t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
        raw = [{"x": float(100 * np.cos(a)), "y": float(50 * np.sin(a))} for a in t]

        result = extract_circuit_centerline(
            raw,
            num_segments=6,
            interpolation_points=2000,
            source_driver=1,
            source_lap=3,
        )

        assert len(result.points) == 2000
        assert len(result.segments) == 6
        assert result.source_driver == 1
        assert result.source_lap == 3

    def test_cumulative_dist_monotonic(self):
        """Cumulative distances are monotonically increasing."""
        t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
        raw = [{"x": float(100 * np.cos(a)), "y": float(50 * np.sin(a))} for a in t]

        result = extract_circuit_centerline(raw)

        dists = [p.cumulative_dist for p in result.points]
        assert dists[0] == 0.0
        for i in range(1, len(dists)):
            assert dists[i] >= dists[i - 1]

    def test_performance_2000_points(self):
        """Extraction completes in under 2 seconds for ~2000 raw points."""
        import time

        t = np.linspace(0, 2 * np.pi, 2000, endpoint=False)
        raw = [{"x": float(100 * np.cos(a)), "y": float(50 * np.sin(a))} for a in t]

        start = time.perf_counter()
        extract_circuit_centerline(raw)
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"Extraction took {elapsed:.2f}s, expected < 2s"

    def test_bounds_contain_all_points(self):
        """Bounding box contains all centerline points."""
        t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
        raw = [{"x": float(100 * np.cos(a)), "y": float(50 * np.sin(a))} for a in t]

        result = extract_circuit_centerline(raw)

        for p in result.points:
            assert result.bounds["min_x"] <= p.x <= result.bounds["max_x"]
            assert result.bounds["min_y"] <= p.y <= result.bounds["max_y"]
