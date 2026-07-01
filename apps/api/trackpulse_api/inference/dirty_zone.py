from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import exp, log
from typing import Mapping, Sequence

TRIGGER_YELLOW = "yellow_flag"
TRIGGER_DOUBLE_YELLOW = "double_yellow_flag"
TRIGGER_INCIDENT_MESSAGE = "incident_message"
TRIGGER_DEBRIS_MESSAGE = "debris_message"
TRIGGER_SAFETY_CAR = "safety_car_or_vsc"

INFERRED_LABEL = "inferred"

_BASE_TRIGGER_PROBABILITY: dict[str, float] = {
    TRIGGER_YELLOW: 0.35,
    TRIGGER_DOUBLE_YELLOW: 0.55,
    TRIGGER_INCIDENT_MESSAGE: 0.5,
    TRIGGER_DEBRIS_MESSAGE: 0.75,
    TRIGGER_SAFETY_CAR: 0.65,
}


@dataclass(frozen=True)
class DirtyZoneInput:
    """Minimal race-control context required for dirty-zone scoring."""

    event_time: datetime
    sector: int | None
    flag: str | None = None
    category: str | None = None
    message: str | None = None
    slowdown_confirmed: bool = False


@dataclass(frozen=True)
class DirtyZoneSegmentProbability:
    segment_id: str
    probability: float
    confidence: float


@dataclass(frozen=True)
class DirtyZoneResult:
    label: str
    trigger: str | None
    debris_confirmed: bool
    age_seconds: float
    expires_at_seconds: float
    segments: tuple[DirtyZoneSegmentProbability, ...]


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _select_trigger(flag: str, category: str, message: str) -> str | None:
    if "double yellow" in flag or "double yellow" in message:
        return TRIGGER_DOUBLE_YELLOW
    if "yellow" in flag:
        return TRIGGER_YELLOW
    if "debris" in message:
        return TRIGGER_DEBRIS_MESSAGE
    if "incident" in message:
        return TRIGGER_INCIDENT_MESSAGE

    safety_car_markers = ("safety car", "virtual safety car", "vsc")
    if any(marker in flag for marker in safety_car_markers):
        return TRIGGER_SAFETY_CAR
    if any(marker in category for marker in safety_car_markers):
        return TRIGGER_SAFETY_CAR
    if any(marker in message for marker in safety_car_markers):
        return TRIGGER_SAFETY_CAR

    return None


def infer_dirty_zone_probability(
    dirty_input: DirtyZoneInput,
    sector_to_segments: Mapping[int, Sequence[str]],
    *,
    now: datetime,
    decay_half_life_seconds: float = 120.0,
    expiry_seconds: float = 600.0,
) -> DirtyZoneResult:
    """Infer per-segment dirty-zone probability from race-control context.

    Assumptions for TP-INF-03 v1:
    - sector-scoped race-control events only affect mapped segments;
    - trigger base-probabilities are deterministic heuristics;
    - probability decays exponentially over time and expires at a fixed horizon;
    - debris is *confirmed* only when race-control text explicitly says "debris".
    """
    flag = _normalize_text(dirty_input.flag)
    category = _normalize_text(dirty_input.category)
    message = _normalize_text(dirty_input.message)

    trigger = _select_trigger(flag, category, message)
    age_seconds = max(0.0, (now - dirty_input.event_time).total_seconds())

    segments_for_sector = tuple(
        sector_to_segments.get(dirty_input.sector, ()) if dirty_input.sector is not None else ()
    )
    if trigger is None or age_seconds >= expiry_seconds or not segments_for_sector:
        return DirtyZoneResult(
            label=INFERRED_LABEL,
            trigger=trigger,
            debris_confirmed=("debris" in message),
            age_seconds=age_seconds,
            expires_at_seconds=expiry_seconds,
            segments=(),
        )

    decay_factor = exp(-log(2.0) * (age_seconds / max(decay_half_life_seconds, 1.0)))
    probability = round(_BASE_TRIGGER_PROBABILITY[trigger] * decay_factor, 4)

    confidence = 0.6
    if trigger in (TRIGGER_DOUBLE_YELLOW, TRIGGER_DEBRIS_MESSAGE, TRIGGER_SAFETY_CAR):
        confidence += 0.1
    if dirty_input.slowdown_confirmed:
        confidence += 0.15

    bounded_confidence = round(min(1.0, confidence), 2)

    return DirtyZoneResult(
        label=INFERRED_LABEL,
        trigger=trigger,
        debris_confirmed=("debris" in message),
        age_seconds=age_seconds,
        expires_at_seconds=expiry_seconds,
        segments=tuple(
            DirtyZoneSegmentProbability(
                segment_id=segment_id,
                probability=probability,
                confidence=bounded_confidence,
            )
            for segment_id in segments_for_sector
        ),
    )