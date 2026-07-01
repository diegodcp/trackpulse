from __future__ import annotations

from dataclasses import dataclass
from math import isnan

REASON_PIT_CONTAMINATION = "pit_contamination"
REASON_RACE_CONTROL_CONTAMINATION = "race_control_contamination"
REASON_HIGH_TRAFFIC = "high_traffic"
REASON_MISSING_SPEED = "missing_speed"
REASON_OBVIOUS_ANOMALY = "obvious_anomaly"


@dataclass(frozen=True)
class CleanSampleInput:
    """Minimal sample fields required for TP-INF-01 clean filtering."""

    pit_contaminated: bool = False
    race_control_contaminated: bool = False
    traffic_score: float = 0.0
    speed_kmh: float | None = None
    has_obvious_anomaly: bool = False


@dataclass(frozen=True)
class CleanSampleResult:
    is_clean: bool
    reasons: tuple[str, ...]
    confidence: float


def _is_missing_speed(speed_kmh: float | None) -> bool:
    return speed_kmh is None or isnan(speed_kmh)


def evaluate_clean_sample(
    sample: CleanSampleInput,
    *,
    traffic_reject_threshold: float = 30.0,
) -> CleanSampleResult:
    """Return whether a sample is clean for downstream inference.

    Rejection order is deterministic and follows TP-INF-01 requirements:
    pit contamination, race-control contamination, high traffic, missing speed,
    and obvious anomaly.

    Confidence is a deterministic heuristic for the filter decision itself.
    """
    reasons: list[str] = []

    if sample.pit_contaminated:
        reasons.append(REASON_PIT_CONTAMINATION)
    if sample.race_control_contaminated:
        reasons.append(REASON_RACE_CONTROL_CONTAMINATION)
    if sample.traffic_score >= traffic_reject_threshold:
        reasons.append(REASON_HIGH_TRAFFIC)
    if _is_missing_speed(sample.speed_kmh):
        reasons.append(REASON_MISSING_SPEED)
    if sample.has_obvious_anomaly:
        reasons.append(REASON_OBVIOUS_ANOMALY)

    is_clean = len(reasons) == 0
    confidence = 1.0 if is_clean else round(min(1.0, 0.65 + (0.1 * len(reasons))), 2)

    return CleanSampleResult(is_clean=is_clean, reasons=tuple(reasons), confidence=confidence)