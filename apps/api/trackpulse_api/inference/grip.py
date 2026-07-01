from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from statistics import median, pstdev

TRACK_EVOLUTION_INSUFFICIENT = "insufficient_clean_samples"
TRACK_EVOLUTION_IMPROVING = "improving"
TRACK_EVOLUTION_WORSENING = "worsening"
TRACK_EVOLUTION_UNSTABLE = "unstable"
TRACK_EVOLUTION_STABLE = "stable"


@dataclass(frozen=True)
class GripSample:
    """Minimal sample required for TP-INF-02 grip evolution scoring."""

    speed_kmh: float | None
    is_clean: bool


@dataclass(frozen=True)
class GripEvolutionResult:
    grip_index: float
    track_evolution: str
    confidence: float
    evidence: dict[str, float | int]


def _valid_clean_speeds(samples: list[GripSample]) -> list[float]:
    return [
        sample.speed_kmh
        for sample in samples
        if sample.is_clean and sample.speed_kmh is not None and not isnan(sample.speed_kmh)
    ]


def score_grip_evolution(
    samples: list[GripSample],
    *,
    min_clean_samples: int = 6,
    median_delta_threshold_kmh: float = 1.0,
    high_variance_threshold_kmh: float = 4.0,
) -> GripEvolutionResult:
    """Score grip evolution from clean segment-speed samples.

    Algorithm v1 (TP-INF-02):
    - only clean samples are considered;
    - at least 6 clean samples are required;
    - compare recent median speed versus previous median speed;
    - +1.0 grip index for improving, -1.0 for worsening;
    - high variance marks the segment as unstable;
    - otherwise classify as stable.

    Assumption: variance is measured as population standard deviation over the
    clean speed window, and values >= 4.0 km/h are considered unstable by
    default for this v1 heuristic.
    """
    clean_speeds = _valid_clean_speeds(samples)
    contaminated_ignored_count = len(samples) - len(clean_speeds)

    if len(clean_speeds) < min_clean_samples:
        return GripEvolutionResult(
            grip_index=0.0,
            track_evolution=TRACK_EVOLUTION_INSUFFICIENT,
            confidence=round(min(0.5, len(clean_speeds) / max(1.0, float(min_clean_samples))), 2),
            evidence={
                "cleanSampleCount": len(clean_speeds),
                "minCleanSamples": min_clean_samples,
                "contaminatedIgnoredCount": contaminated_ignored_count,
            },
        )

    window_size = len(clean_speeds) // 2
    previous_window = clean_speeds[-(2 * window_size) : -window_size]
    recent_window = clean_speeds[-window_size:]

    previous_median = median(previous_window)
    recent_median = median(recent_window)
    median_delta = round(recent_median - previous_median, 2)
    speed_std_dev = round(pstdev(clean_speeds), 2)

    track_evolution = TRACK_EVOLUTION_STABLE
    grip_index = 0.0
    confidence = 0.7

    if speed_std_dev >= high_variance_threshold_kmh:
        track_evolution = TRACK_EVOLUTION_UNSTABLE
        confidence = 0.45
    elif median_delta >= median_delta_threshold_kmh:
        track_evolution = TRACK_EVOLUTION_IMPROVING
        grip_index = 1.0
        confidence = 0.8
    elif median_delta <= -median_delta_threshold_kmh:
        track_evolution = TRACK_EVOLUTION_WORSENING
        grip_index = -1.0
        confidence = 0.8

    return GripEvolutionResult(
        grip_index=grip_index,
        track_evolution=track_evolution,
        confidence=confidence,
        evidence={
            "cleanSampleCount": len(clean_speeds),
            "previousMedianSpeedKmh": round(previous_median, 2),
            "recentMedianSpeedKmh": round(recent_median, 2),
            "medianDeltaKmh": median_delta,
            "speedStdDevKmh": speed_std_dev,
            "contaminatedIgnoredCount": contaminated_ignored_count,
        },
    )
