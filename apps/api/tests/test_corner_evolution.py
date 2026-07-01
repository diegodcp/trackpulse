from __future__ import annotations

import pytest

from trackpulse_api.inference.corner_evolution import (
    CORNER_EVOLUTION_IMPROVING,
    CORNER_EVOLUTION_INSUFFICIENT_DATA,
    CORNER_EVOLUTION_STABLE,
    CORNER_EVOLUTION_WORSENING,
    INFERRED_LABEL,
    CornerSpeedSample,
    score_corner_evolution,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEG = "T3"


def _samples(speeds: list[float], contaminated: list[bool] | None = None) -> list[CornerSpeedSample]:
    if contaminated is None:
        contaminated = [False] * len(speeds)
    return [
        CornerSpeedSample(segment_id=SEG, speed_kmh=s, is_contaminated=c)
        for s, c in zip(speeds, contaminated)
    ]


# ---------------------------------------------------------------------------
# Insufficient data
# ---------------------------------------------------------------------------


def test_insufficient_data_when_no_samples() -> None:
    result = score_corner_evolution([])
    assert result.evolution == CORNER_EVOLUTION_INSUFFICIENT_DATA
    assert result.confidence == pytest.approx(0.0)
    assert result.avg_speed_delta_kmh == pytest.approx(0.0)
    assert result.label == INFERRED_LABEL


def test_insufficient_data_below_min_samples() -> None:
    result = score_corner_evolution(_samples([100.0, 101.0, 102.0]))  # 3 < default 4
    assert result.evolution == CORNER_EVOLUTION_INSUFFICIENT_DATA
    assert result.label == INFERRED_LABEL
    assert result.evidence["cleanSampleCount"] == 3


def test_insufficient_data_low_confidence() -> None:
    result = score_corner_evolution(_samples([100.0]))
    assert result.confidence < 0.4
    assert result.evolution == CORNER_EVOLUTION_INSUFFICIENT_DATA


def test_insufficient_data_all_contaminated() -> None:
    result = score_corner_evolution(
        _samples([100.0, 101.0, 102.0, 103.0], contaminated=[True, True, True, True])
    )
    assert result.evolution == CORNER_EVOLUTION_INSUFFICIENT_DATA
    assert result.evidence["cleanSampleCount"] == 0
    assert result.evidence["contaminatedCount"] == 4


# ---------------------------------------------------------------------------
# Improving
# ---------------------------------------------------------------------------


def test_improving_speeds_detected() -> None:
    # Baseline lower, current higher by >0.5 km/h
    result = score_corner_evolution(
        _samples([98.0, 98.5, 99.0, 99.5, 100.5, 101.0, 101.5, 102.0])
    )
    assert result.evolution == CORNER_EVOLUTION_IMPROVING
    assert result.avg_speed_delta_kmh > 0.5
    assert result.label == INFERRED_LABEL
    assert result.evidence["avgCurrentKmh"] > result.evidence["avgBaselineKmh"]


def test_improving_minimum_qualifying_samples() -> None:
    # Exactly 4 samples: baseline [90, 90], current [91, 91] → delta = 1.0
    result = score_corner_evolution(_samples([90.0, 90.0, 91.0, 91.0]))
    assert result.evolution == CORNER_EVOLUTION_IMPROVING
    assert result.avg_speed_delta_kmh == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Worsening
# ---------------------------------------------------------------------------


def test_worsening_speeds_detected() -> None:
    result = score_corner_evolution(
        _samples([102.0, 101.5, 101.0, 100.5, 99.5, 99.0, 98.5, 98.0])
    )
    assert result.evolution == CORNER_EVOLUTION_WORSENING
    assert result.avg_speed_delta_kmh < -0.5
    assert result.label == INFERRED_LABEL
    assert result.evidence["avgCurrentKmh"] < result.evidence["avgBaselineKmh"]


def test_worsening_minimum_qualifying_samples() -> None:
    # Baseline [91, 91], current [90, 90] → delta = -1.0
    result = score_corner_evolution(_samples([91.0, 91.0, 90.0, 90.0]))
    assert result.evolution == CORNER_EVOLUTION_WORSENING
    assert result.avg_speed_delta_kmh == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# Stable
# ---------------------------------------------------------------------------


def test_stable_when_delta_below_threshold() -> None:
    # All speeds nearly identical — delta well below 0.5 km/h
    result = score_corner_evolution(
        _samples([100.0, 100.1, 100.0, 100.1, 100.0, 100.1, 100.0, 100.1])
    )
    assert result.evolution == CORNER_EVOLUTION_STABLE
    assert abs(result.avg_speed_delta_kmh) < 0.5
    assert result.label == INFERRED_LABEL


def test_stable_custom_threshold() -> None:
    # delta = 0.5; just below a threshold of 0.6 → stable
    result = score_corner_evolution(
        _samples([100.0, 100.0, 100.5, 100.5]),
        delta_threshold_kmh=0.6,
    )
    assert result.evolution == CORNER_EVOLUTION_STABLE


# ---------------------------------------------------------------------------
# Noisy / contaminated samples
# ---------------------------------------------------------------------------


def test_contaminated_samples_excluded_from_scoring() -> None:
    # Two very fast contaminated readings that would skew the average.
    # Without them, speeds are stable near 100 km/h.
    clean_part = [100.0, 100.1, 99.9, 100.0]
    contaminated_part = [200.0, 200.0]
    speeds = contaminated_part + clean_part
    flags = [True, True] + [False] * 4
    result = score_corner_evolution(_samples(speeds, contaminated=flags))

    # Should not be improving despite the outlier contaminated readings.
    assert result.evolution == CORNER_EVOLUTION_STABLE
    assert result.evidence["cleanSampleCount"] == 4
    assert result.evidence["contaminatedCount"] == 2


def test_high_contamination_reduces_confidence() -> None:
    # 4 clean samples (exactly min) but 8 contaminated → lower confidence
    clean = [100.0, 100.0, 100.5, 100.5]
    dirty = [200.0] * 8
    speeds = dirty + clean
    flags = [True] * 8 + [False] * 4
    result = score_corner_evolution(_samples(speeds, contaminated=flags))

    low_result = result
    # Compare against a result with no contamination but same clean samples.
    pure_result = score_corner_evolution(_samples(clean))
    assert low_result.confidence < pure_result.confidence


def test_noisy_speeds_stable_classification() -> None:
    # Alternating high/low but symmetric → avg delta ~0 → stable
    result = score_corner_evolution(
        _samples([95.0, 105.0, 95.0, 105.0, 95.0, 105.0, 95.0, 105.0])
    )
    assert result.evolution == CORNER_EVOLUTION_STABLE
    assert abs(result.avg_speed_delta_kmh) < 0.5


# ---------------------------------------------------------------------------
# Label and evidence
# ---------------------------------------------------------------------------


def test_result_always_inferred() -> None:
    result = score_corner_evolution(_samples([100.0, 100.0, 100.0, 100.0]))
    assert result.label == INFERRED_LABEL


def test_evidence_keys_present_on_valid_result() -> None:
    result = score_corner_evolution(
        _samples([100.0, 100.0, 101.0, 101.0, 102.0, 102.0, 103.0, 103.0])
    )
    assert "cleanSampleCount" in result.evidence
    assert "avgBaselineKmh" in result.evidence
    assert "avgCurrentKmh" in result.evidence
    assert "contaminatedCount" in result.evidence


def test_evidence_keys_present_on_insufficient_result() -> None:
    result = score_corner_evolution(_samples([100.0, 101.0]))
    assert "cleanSampleCount" in result.evidence
    assert "minSamples" in result.evidence
    assert "contaminatedCount" in result.evidence


def test_segment_id_preserved_in_result() -> None:
    samples = [CornerSpeedSample(segment_id="S1", speed_kmh=100.0 + i * 0.5, is_contaminated=False) for i in range(8)]
    result = score_corner_evolution(samples)
    assert result.segment_id == "S1"
