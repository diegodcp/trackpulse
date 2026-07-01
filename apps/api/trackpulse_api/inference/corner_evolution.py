from __future__ import annotations

from dataclasses import dataclass
from math import isnan

CORNER_EVOLUTION_IMPROVING = "improving"
CORNER_EVOLUTION_STABLE = "stable"
CORNER_EVOLUTION_WORSENING = "worsening"
CORNER_EVOLUTION_INSUFFICIENT_DATA = "insufficient_data"

INFERRED_LABEL = "inferred"


@dataclass(frozen=True)
class CornerSpeedSample:
    """A single speed observation assigned to a segment.

    Attributes:
        segment_id: The segment identifier this observation belongs to.
        speed_kmh: Car speed from car_data in km/h. None if unavailable.
        is_contaminated: True if the sample should be excluded from evolution
            scoring (e.g. pit-out lap, safety car, VSC, race control event).
    """

    segment_id: str
    speed_kmh: float | None
    is_contaminated: bool = False


@dataclass(frozen=True)
class CornerEvolutionResult:
    """Rolling corner evolution result for a single segment.

    Attributes:
        segment_id: The segment this result applies to.
        avg_speed_delta_kmh: Average speed current window minus baseline window
            in km/h. Positive means faster, negative means slower.
        evolution: One of ``improving``, ``stable``, ``worsening``, or
            ``insufficient_data``.
        confidence: Heuristic confidence in [0.0, 1.0].
        label: Always ``"inferred"`` — never present this as measured.
        evidence: Diagnostic counters and intermediate values.
    """

    segment_id: str
    avg_speed_delta_kmh: float
    evolution: str
    confidence: float
    label: str
    evidence: dict[str, float | int]


def _valid_clean_speeds(samples: list[CornerSpeedSample]) -> list[float]:
    return [
        s.speed_kmh
        for s in samples
        if not s.is_contaminated
        and s.speed_kmh is not None
        and not isnan(s.speed_kmh)
    ]


def _avg(values: list[float]) -> float:
    return sum(values) / len(values)


def score_corner_evolution(
    samples: list[CornerSpeedSample],
    *,
    min_samples: int = 4,
    delta_threshold_kmh: float = 0.5,
) -> CornerEvolutionResult:
    """Score rolling corner evolution for a single segment.

    Algorithm (TP-BH-0017):
    - Contaminated and missing-speed samples are excluded.
    - At least ``min_samples`` clean observations are required; otherwise the
      result is ``insufficient_data`` with confidence proportional to sample
      count.
    - Clean samples are split chronologically: the older half forms the
      *baseline* window and the more recent half forms the *current* window.
    - ``avg_speed_delta_kmh = avg(current) - avg(baseline)``.
    - If delta >=  ``delta_threshold_kmh`` → improving.
    - If delta <= -``delta_threshold_kmh`` → worsening.
    - Otherwise → stable.
    - Confidence rises with sample count and falls when many samples are
      contaminated.

    Assumption (TP-BH-0017): A minimum of 4 clean samples is sufficient for a
    v1 heuristic. ``delta_threshold_kmh`` defaults to 0.5 km/h because corner
    segments typically have lower absolute speeds than straights.
    """
    segment_id = samples[0].segment_id if samples else ""
    contaminated_count = sum(1 for s in samples if s.is_contaminated)
    clean_speeds = _valid_clean_speeds(samples)
    clean_count = len(clean_speeds)

    if clean_count < min_samples:
        confidence = round(
            min(0.4, clean_count / max(1, min_samples) * 0.4), 2
        )
        return CornerEvolutionResult(
            segment_id=segment_id,
            avg_speed_delta_kmh=0.0,
            evolution=CORNER_EVOLUTION_INSUFFICIENT_DATA,
            confidence=confidence,
            label=INFERRED_LABEL,
            evidence={
                "cleanSampleCount": clean_count,
                "minSamples": min_samples,
                "contaminatedCount": contaminated_count,
            },
        )

    # Split chronologically into baseline (older) and current (recent) halves.
    window_size = clean_count // 2
    baseline_window = clean_speeds[:window_size]
    current_window = clean_speeds[window_size : window_size * 2]

    avg_baseline = _avg(baseline_window)
    avg_current = _avg(current_window)
    avg_speed_delta = round(avg_current - avg_baseline, 3)

    if avg_speed_delta >= delta_threshold_kmh:
        evolution = CORNER_EVOLUTION_IMPROVING
    elif avg_speed_delta <= -delta_threshold_kmh:
        evolution = CORNER_EVOLUTION_WORSENING
    else:
        evolution = CORNER_EVOLUTION_STABLE

    # Confidence heuristic: scales from 0.55 at min_samples toward 0.9 at
    # 20+ clean samples, then penalised proportionally to contamination ratio.
    raw_confidence = min(0.9, 0.55 + 0.35 * (clean_count - min_samples) / max(1, 20 - min_samples))
    total_samples = len(samples)
    contamination_ratio = contaminated_count / max(1, total_samples)
    confidence = round(raw_confidence * (1.0 - 0.4 * contamination_ratio), 2)

    return CornerEvolutionResult(
        segment_id=segment_id,
        avg_speed_delta_kmh=avg_speed_delta,
        evolution=evolution,
        confidence=confidence,
        label=INFERRED_LABEL,
        evidence={
            "cleanSampleCount": clean_count,
            "minSamples": min_samples,
            "contaminatedCount": contaminated_count,
            "avgBaselineKmh": round(avg_baseline, 2),
            "avgCurrentKmh": round(avg_current, 2),
        },
    )
