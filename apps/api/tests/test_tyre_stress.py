from __future__ import annotations

import pytest

from trackpulse_api.inference.tyre import (
    INFERRED_LABEL,
    TYRE_STRESS_HIGH,
    TYRE_STRESS_LOW,
    TYRE_STRESS_UNKNOWN,
    TyreStint,
    TyreStressSample,
    score_tyre_stress,
)


def test_missing_stint_returns_low_confidence() -> None:
    result = score_tyre_stress(
        [
            TyreStressSample(speed_kmh=210.0, throttle_delay_seconds=0.10, is_clean=True),
            TyreStressSample(speed_kmh=209.5, throttle_delay_seconds=0.10, is_clean=True),
            TyreStressSample(speed_kmh=210.2, throttle_delay_seconds=0.11, is_clean=True),
            TyreStressSample(speed_kmh=209.8, throttle_delay_seconds=0.11, is_clean=True),
            TyreStressSample(speed_kmh=209.4, throttle_delay_seconds=0.10, is_clean=True),
            TyreStressSample(speed_kmh=209.6, throttle_delay_seconds=0.11, is_clean=True),
        ],
        lap_number=12,
        stints=[],
        compound="MEDIUM",
        tyre_age_at_start=4,
    )

    assert result.label == INFERRED_LABEL
    assert result.stress_level in {TYRE_STRESS_LOW, TYRE_STRESS_UNKNOWN}
    assert result.confidence == pytest.approx(0.35)
    assert result.tyre_age_laps == 4
    assert result.evidence["missingStint"] is True


def test_stable_clean_segment_window_scores_low_stress() -> None:
    result = score_tyre_stress(
        [
            TyreStressSample(speed_kmh=210.0, throttle_delay_seconds=0.10, is_clean=True),
            TyreStressSample(speed_kmh=209.8, throttle_delay_seconds=0.10, is_clean=True),
            TyreStressSample(speed_kmh=210.1, throttle_delay_seconds=0.10, is_clean=True),
            TyreStressSample(speed_kmh=209.9, throttle_delay_seconds=0.10, is_clean=True),
            TyreStressSample(speed_kmh=209.7, throttle_delay_seconds=0.11, is_clean=True),
            TyreStressSample(speed_kmh=210.0, throttle_delay_seconds=0.10, is_clean=True),
        ],
        lap_number=10,
        stints=[TyreStint(lap_start=5, lap_end=18, compound="MEDIUM", tyre_age_at_start=2)],
    )

    assert result.label == INFERRED_LABEL
    assert result.stress_level == TYRE_STRESS_LOW
    assert result.stress_score < 35.0
    assert result.confidence == pytest.approx(0.8)
    assert result.tyre_age_laps == 7
    assert result.evidence["exitSpeedLossKmh"] < 1.0
    assert result.evidence["throttleDelayIncreaseSeconds"] <= 0.01


def test_degradation_window_scores_high_stress() -> None:
    result = score_tyre_stress(
        [
            TyreStressSample(speed_kmh=211.0, throttle_delay_seconds=0.08, is_clean=True),
            TyreStressSample(speed_kmh=210.5, throttle_delay_seconds=0.08, is_clean=True),
            TyreStressSample(speed_kmh=210.0, throttle_delay_seconds=0.09, is_clean=True),
            TyreStressSample(speed_kmh=203.0, throttle_delay_seconds=0.19, is_clean=True),
            TyreStressSample(speed_kmh=202.5, throttle_delay_seconds=0.21, is_clean=True),
            TyreStressSample(speed_kmh=202.0, throttle_delay_seconds=0.20, is_clean=True),
        ],
        lap_number=24,
        stints=[TyreStint(lap_start=10, lap_end=30, compound="HARD", tyre_age_at_start=6)],
    )

    assert result.stress_level == TYRE_STRESS_HIGH
    assert result.stress_score >= 65.0
    assert result.tyre_age_laps == 20
    assert result.evidence["exitSpeedLossKmh"] >= 7.0
    assert result.evidence["throttleDelayIncreaseSeconds"] >= 0.1


def test_contaminated_samples_are_ignored() -> None:
    clean_window = [
        TyreStressSample(speed_kmh=210.0, throttle_delay_seconds=0.10, is_clean=True),
        TyreStressSample(speed_kmh=209.8, throttle_delay_seconds=0.10, is_clean=True),
        TyreStressSample(speed_kmh=210.1, throttle_delay_seconds=0.10, is_clean=True),
        TyreStressSample(speed_kmh=209.9, throttle_delay_seconds=0.10, is_clean=True),
        TyreStressSample(speed_kmh=209.7, throttle_delay_seconds=0.11, is_clean=True),
        TyreStressSample(speed_kmh=210.0, throttle_delay_seconds=0.10, is_clean=True),
    ]
    with_traffic = [
        TyreStressSample(speed_kmh=150.0, throttle_delay_seconds=0.50, is_clean=False),
        *clean_window,
        TyreStressSample(speed_kmh=280.0, throttle_delay_seconds=0.01, is_clean=False),
    ]

    clean_result = score_tyre_stress(
        clean_window,
        lap_number=10,
        stints=[TyreStint(lap_start=5, lap_end=18, compound="MEDIUM", tyre_age_at_start=2)],
    )
    contaminated_result = score_tyre_stress(
        with_traffic,
        lap_number=10,
        stints=[TyreStint(lap_start=5, lap_end=18, compound="MEDIUM", tyre_age_at_start=2)],
    )

    assert contaminated_result.stress_level == clean_result.stress_level
    assert contaminated_result.stress_score == pytest.approx(clean_result.stress_score)
    assert contaminated_result.evidence["contaminatedIgnoredCount"] == 2