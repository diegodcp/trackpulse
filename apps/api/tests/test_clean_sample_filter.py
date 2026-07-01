from __future__ import annotations

from trackpulse_api.inference.clean_sample import (
    CleanSampleInput,
    REASON_HIGH_TRAFFIC,
    REASON_MISSING_SPEED,
    REASON_OBVIOUS_ANOMALY,
    REASON_PIT_CONTAMINATION,
    REASON_RACE_CONTROL_CONTAMINATION,
    evaluate_clean_sample,
)


def test_rejects_pit_contamination() -> None:
    result = evaluate_clean_sample(
        CleanSampleInput(
            pit_contaminated=True,
            speed_kmh=210.0,
        )
    )

    assert result.is_clean is False
    assert result.reasons == (REASON_PIT_CONTAMINATION,)
    assert 0.0 < result.confidence <= 1.0


def test_rejects_race_control_contamination() -> None:
    result = evaluate_clean_sample(
        CleanSampleInput(
            race_control_contaminated=True,
            speed_kmh=210.0,
        )
    )

    assert result.is_clean is False
    assert result.reasons == (REASON_RACE_CONTROL_CONTAMINATION,)
    assert 0.0 < result.confidence <= 1.0


def test_rejects_high_traffic_at_threshold() -> None:
    result = evaluate_clean_sample(
        CleanSampleInput(
            traffic_score=30.0,
            speed_kmh=210.0,
        )
    )

    assert result.is_clean is False
    assert result.reasons == (REASON_HIGH_TRAFFIC,)
    assert 0.0 < result.confidence <= 1.0


def test_rejects_missing_speed() -> None:
    result = evaluate_clean_sample(
        CleanSampleInput(
            speed_kmh=None,
        )
    )

    assert result.is_clean is False
    assert result.reasons == (REASON_MISSING_SPEED,)
    assert 0.0 < result.confidence <= 1.0


def test_rejects_obvious_anomaly() -> None:
    result = evaluate_clean_sample(
        CleanSampleInput(
            speed_kmh=210.0,
            has_obvious_anomaly=True,
        )
    )

    assert result.is_clean is False
    assert result.reasons == (REASON_OBVIOUS_ANOMALY,)
    assert 0.0 < result.confidence <= 1.0


def test_accepts_clean_sample() -> None:
    result = evaluate_clean_sample(
        CleanSampleInput(
            pit_contaminated=False,
            race_control_contaminated=False,
            traffic_score=12.0,
            speed_kmh=210.0,
            has_obvious_anomaly=False,
        )
    )

    assert result.is_clean is True
    assert result.reasons == ()
    assert result.confidence == 1.0