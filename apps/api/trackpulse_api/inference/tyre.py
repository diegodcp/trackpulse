from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from statistics import median

INFERRED_LABEL = "inferred"

TYRE_STRESS_LOW = "low"
TYRE_STRESS_MEDIUM = "medium"
TYRE_STRESS_HIGH = "high"
TYRE_STRESS_UNKNOWN = "unknown"


@dataclass(frozen=True)
class TyreStint:
    lap_start: int | None
    lap_end: int | None
    compound: str | None = None
    tyre_age_at_start: int | None = None


@dataclass(frozen=True)
class TyreStressSample:
    speed_kmh: float | None
    throttle_delay_seconds: float | None
    is_clean: bool


@dataclass(frozen=True)
class TyreStressResult:
    label: str
    stress_score: float
    stress_level: str
    confidence: float
    tyre_age_laps: int | None
    compound: str | None
    evidence: dict[str, float | int | str | bool | None]


def _is_valid_number(value: float | None) -> bool:
    return value is not None and not isnan(value)


def _is_stint_active(stint: TyreStint, lap_number: int) -> bool:
    if stint.lap_start is None:
        return False

    if lap_number < stint.lap_start:
        return False

    if stint.lap_end is not None and lap_number > stint.lap_end:
        return False

    return True


def _resolve_active_stint(stints: list[TyreStint], lap_number: int) -> TyreStint | None:
    for stint in stints:
        if _is_stint_active(stint, lap_number):
            return stint

    return None


def _window_median(values: list[float], *, use_recent: bool, window_size: int) -> float:
    window = values[-window_size:] if use_recent else values[:window_size]
    return round(median(window), 2)


def score_tyre_stress(
    segment_samples: list[TyreStressSample],
    *,
    lap_number: int,
    stints: list[TyreStint],
    compound: str | None = None,
    tyre_age_at_start: int | None = None,
    min_clean_samples: int = 6,
    comparison_window_size: int = 3,
) -> TyreStressResult:
    """Infer a generic tyre-stress score from stint context and clean segment samples.

    Assumption for TP-INF-04 v1: ``segment_samples`` are ordered from early-stint
    baseline samples to the most recent samples for the same segment, so the first
    clean window acts as the baseline and the last clean window acts as the recent view.
    """
    active_stint = _resolve_active_stint(stints, lap_number)
    resolved_compound = compound or (active_stint.compound if active_stint is not None else None)

    resolved_tyre_age_start = tyre_age_at_start
    if resolved_tyre_age_start is None and active_stint is not None:
        resolved_tyre_age_start = active_stint.tyre_age_at_start

    tyre_age_laps: int | None = None
    if active_stint is not None and active_stint.lap_start is not None and resolved_tyre_age_start is not None:
        tyre_age_laps = resolved_tyre_age_start + max(0, lap_number - active_stint.lap_start)
    elif resolved_tyre_age_start is not None:
        tyre_age_laps = resolved_tyre_age_start

    clean_samples = [sample for sample in segment_samples if sample.is_clean and _is_valid_number(sample.speed_kmh)]
    contaminated_ignored_count = len(segment_samples) - len(clean_samples)

    if len(clean_samples) < min_clean_samples:
        confidence = 0.25 if active_stint is None else 0.45
        return TyreStressResult(
            label=INFERRED_LABEL,
            stress_score=0.0,
            stress_level=TYRE_STRESS_UNKNOWN,
            confidence=confidence,
            tyre_age_laps=tyre_age_laps,
            compound=resolved_compound,
            evidence={
                "cleanSampleCount": len(clean_samples),
                "minCleanSamples": min_clean_samples,
                "contaminatedIgnoredCount": contaminated_ignored_count,
                "missingStint": active_stint is None,
            },
        )

    speeds = [sample.speed_kmh for sample in clean_samples if sample.speed_kmh is not None]
    delays = [sample.throttle_delay_seconds for sample in clean_samples if _is_valid_number(sample.throttle_delay_seconds)]

    window_size = min(comparison_window_size, len(speeds) // 2)
    baseline_speed = _window_median(speeds, use_recent=False, window_size=window_size)
    recent_speed = _window_median(speeds, use_recent=True, window_size=window_size)
    exit_speed_loss = round(max(0.0, baseline_speed - recent_speed), 2)

    baseline_delay = 0.0
    recent_delay = 0.0
    throttle_delay_increase = 0.0
    if len(delays) >= max(2, window_size * 2):
        baseline_delay = _window_median(delays, use_recent=False, window_size=window_size)
        recent_delay = _window_median(delays, use_recent=True, window_size=window_size)
        throttle_delay_increase = round(max(0.0, recent_delay - baseline_delay), 3)

    speed_component = min(1.0, exit_speed_loss / 6.0)
    delay_component = min(1.0, throttle_delay_increase / 0.12)
    age_component = 0.0 if tyre_age_laps is None else min(1.0, tyre_age_laps / 25.0)

    stress_score = round((speed_component * 55.0) + (delay_component * 30.0) + (age_component * 15.0), 1)

    stress_level = TYRE_STRESS_LOW
    if stress_score >= 65.0:
        stress_level = TYRE_STRESS_HIGH
    elif stress_score >= 35.0:
        stress_level = TYRE_STRESS_MEDIUM

    confidence = 0.8
    if active_stint is None:
        confidence = 0.35
    elif tyre_age_laps is None:
        confidence = 0.65

    return TyreStressResult(
        label=INFERRED_LABEL,
        stress_score=stress_score,
        stress_level=stress_level,
        confidence=confidence,
        tyre_age_laps=tyre_age_laps,
        compound=resolved_compound,
        evidence={
            "cleanSampleCount": len(clean_samples),
            "baselineSpeedKmh": baseline_speed,
            "recentSpeedKmh": recent_speed,
            "exitSpeedLossKmh": exit_speed_loss,
            "baselineThrottleDelaySeconds": baseline_delay,
            "recentThrottleDelaySeconds": recent_delay,
            "throttleDelayIncreaseSeconds": throttle_delay_increase,
            "contaminatedIgnoredCount": contaminated_ignored_count,
            "missingStint": active_stint is None,
        },
    )