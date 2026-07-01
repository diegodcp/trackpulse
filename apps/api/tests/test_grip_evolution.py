from __future__ import annotations

import pytest

from trackpulse_api.inference.grip import (
    GripSample,
    TRACK_EVOLUTION_IMPROVING,
    TRACK_EVOLUTION_INSUFFICIENT,
    TRACK_EVOLUTION_UNSTABLE,
    TRACK_EVOLUTION_WORSENING,
    score_grip_evolution,
)


def test_grip_evolution_insufficient_clean_samples() -> None:
    result = score_grip_evolution(
        [
            GripSample(speed_kmh=200.0, is_clean=True),
            GripSample(speed_kmh=201.0, is_clean=True),
            GripSample(speed_kmh=202.0, is_clean=True),
            GripSample(speed_kmh=203.0, is_clean=True),
            GripSample(speed_kmh=204.0, is_clean=True),
        ]
    )

    assert result.track_evolution == TRACK_EVOLUTION_INSUFFICIENT
    assert result.grip_index == pytest.approx(0.0)
    assert result.evidence["cleanSampleCount"] == 5


def test_grip_evolution_improving() -> None:
    result = score_grip_evolution(
        [
            GripSample(speed_kmh=200.0, is_clean=True),
            GripSample(speed_kmh=201.0, is_clean=True),
            GripSample(speed_kmh=200.5, is_clean=True),
            GripSample(speed_kmh=203.0, is_clean=True),
            GripSample(speed_kmh=203.5, is_clean=True),
            GripSample(speed_kmh=204.0, is_clean=True),
        ],
        high_variance_threshold_kmh=10.0,
    )

    assert result.track_evolution == TRACK_EVOLUTION_IMPROVING
    assert result.grip_index == pytest.approx(1.0)
    assert result.evidence["medianDeltaKmh"] >= 1.0


def test_grip_evolution_worsening() -> None:
    result = score_grip_evolution(
        [
            GripSample(speed_kmh=204.0, is_clean=True),
            GripSample(speed_kmh=203.5, is_clean=True),
            GripSample(speed_kmh=203.0, is_clean=True),
            GripSample(speed_kmh=201.0, is_clean=True),
            GripSample(speed_kmh=200.5, is_clean=True),
            GripSample(speed_kmh=200.0, is_clean=True),
        ],
        high_variance_threshold_kmh=10.0,
    )

    assert result.track_evolution == TRACK_EVOLUTION_WORSENING
    assert result.grip_index == pytest.approx(-1.0)
    assert result.evidence["medianDeltaKmh"] <= -1.0


def test_grip_evolution_unstable_variance() -> None:
    result = score_grip_evolution(
        [
            GripSample(speed_kmh=180.0, is_clean=True),
            GripSample(speed_kmh=220.0, is_clean=True),
            GripSample(speed_kmh=182.0, is_clean=True),
            GripSample(speed_kmh=218.0, is_clean=True),
            GripSample(speed_kmh=181.0, is_clean=True),
            GripSample(speed_kmh=219.0, is_clean=True),
        ],
        high_variance_threshold_kmh=4.0,
    )

    assert result.track_evolution == TRACK_EVOLUTION_UNSTABLE
    assert result.grip_index == pytest.approx(0.0)
    assert result.evidence["speedStdDevKmh"] >= 4.0


def test_grip_evolution_ignores_contaminated_samples() -> None:
    clean_only = [
        GripSample(speed_kmh=200.0, is_clean=True),
        GripSample(speed_kmh=201.0, is_clean=True),
        GripSample(speed_kmh=201.5, is_clean=True),
        GripSample(speed_kmh=203.0, is_clean=True),
        GripSample(speed_kmh=203.5, is_clean=True),
        GripSample(speed_kmh=204.0, is_clean=True),
    ]

    with_contaminated = [
        GripSample(speed_kmh=120.0, is_clean=False),
        *clean_only,
        GripSample(speed_kmh=280.0, is_clean=False),
    ]

    clean_result = score_grip_evolution(clean_only, high_variance_threshold_kmh=10.0)
    contaminated_result = score_grip_evolution(with_contaminated, high_variance_threshold_kmh=10.0)

    assert contaminated_result.track_evolution == clean_result.track_evolution
    assert contaminated_result.grip_index == pytest.approx(clean_result.grip_index)
    assert contaminated_result.evidence["cleanSampleCount"] == clean_result.evidence["cleanSampleCount"]
    assert contaminated_result.evidence["contaminatedIgnoredCount"] == 2
