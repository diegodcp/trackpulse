from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .grip import TRACK_EVOLUTION_IMPROVING, TRACK_EVOLUTION_WORSENING

INSIGHT_CATEGORY_GRIP = "grip"
INSIGHT_CATEGORY_TRAFFIC = "traffic"
INSIGHT_CATEGORY_WIND = "wind"
INSIGHT_CATEGORY_DIRTY_ZONE = "dirty_zone"
INSIGHT_CATEGORY_TYRE_STRESS = "tyre_stress"
INSIGHT_CATEGORY_RAIN = "rain"

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"

LABEL_MEASURED = "measured"
LABEL_DERIVED = "derived"
LABEL_INFERRED = "inferred"

HIGH_WIND_SPEED_THRESHOLD_MS = 8.0
GRIP_CONFIDENCE_THRESHOLD = 0.7
TRAFFIC_SCORE_THRESHOLD = 70.0
DIRTY_ZONE_PROBABILITY_THRESHOLD = 0.5
TYRE_STRESS_SCORE_THRESHOLD = 70.0
RAIN_INFLUENCE_PROBABILITY_THRESHOLD = 0.55


@dataclass(frozen=True)
class GripInsightInput:
    segment_id: str
    track_evolution: str
    confidence: float
    grip_index: float | None = None


@dataclass(frozen=True)
class TrafficInsightInput:
    segment_id: str
    traffic_score: float


@dataclass(frozen=True)
class WindInsightInput:
    segment_id: str
    wind_speed_ms: float | None
    wind_class: str | None
    wind_strength_score: float | None = None


@dataclass(frozen=True)
class DirtyZoneInsightInput:
    segment_ids: tuple[str, ...]
    probability: float
    confidence: float
    trigger: str | None = None


@dataclass(frozen=True)
class TyreStressInsightInput:
    segment_id: str
    stress_score: float
    confidence: float
    stress_level: str | None = None


@dataclass(frozen=True)
class RainInsightInput:
    segment_ids: tuple[str, ...]
    probability: float
    confidence: float
    measured_rainfall: bool | None = None


@dataclass(frozen=True)
class InsightEngineInput:
    grip: tuple[GripInsightInput, ...] = ()
    traffic: tuple[TrafficInsightInput, ...] = ()
    wind: tuple[WindInsightInput, ...] = ()
    dirty_zone: tuple[DirtyZoneInsightInput, ...] = ()
    tyre_stress: tuple[TyreStressInsightInput, ...] = ()
    rain: tuple[RainInsightInput, ...] = ()


@dataclass(frozen=True)
class InsightEngineState:
    last_emitted_at: dict[str, datetime] = field(default_factory=dict)


def _evidence_value(value: Any, label: str) -> dict[str, Any]:
    return {
        "value": value,
        "label": label,
    }


def _insight_payload(
    *,
    category: str,
    severity: str,
    title: str,
    message: str,
    confidence: float,
    segment_ids: tuple[str, ...],
    evidence: dict[str, Any],
    expires_at: datetime,
) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "title": title,
        "message": message,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "segmentIds": list(segment_ids),
        "evidence": evidence,
        "expiresAt": expires_at.isoformat(),
    }


def _dedupe_key(category: str, title: str, segment_ids: tuple[str, ...]) -> str:
    segment_key = ",".join(sorted(segment_ids))
    return f"{category}|{title}|{segment_key}"


def _on_cooldown(
    dedupe_key: str,
    *,
    now: datetime,
    state: InsightEngineState,
    cooldown_seconds: float,
) -> bool:
    last_emitted_at = state.last_emitted_at.get(dedupe_key)
    if last_emitted_at is None:
        return False

    return (now - last_emitted_at).total_seconds() < cooldown_seconds


def _emit_insight(
    insights: list[dict[str, Any]],
    *,
    category: str,
    severity: str,
    title: str,
    message: str,
    confidence: float,
    segment_ids: tuple[str, ...],
    evidence: dict[str, Any],
    now: datetime,
    state: InsightEngineState,
    cooldown_seconds: float,
    ttl_seconds: float,
) -> None:
    key = _dedupe_key(category, title, segment_ids)
    if _on_cooldown(key, now=now, state=state, cooldown_seconds=cooldown_seconds):
        return

    insights.append(
        _insight_payload(
            category=category,
            severity=severity,
            title=title,
            message=message,
            confidence=confidence,
            segment_ids=segment_ids,
            evidence=evidence,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
    )
    state.last_emitted_at[key] = now


def generate_rule_based_insights(
    insight_input: InsightEngineInput,
    *,
    now: datetime,
    state: InsightEngineState | None = None,
    cooldown_seconds: float = 90.0,
    ttl_seconds: float = 45.0,
) -> tuple[list[dict[str, Any]], InsightEngineState]:
    """Generate TP-INS-01 rule-based insights.

    Assumptions:
    - high wind is defined as wind_speed_ms >= 8.0 for v1;
    - wind watch applies when a segment has a known non-unknown wind class;
    - dedupe is keyed by (category, title, segmentIds) and enforced by cooldown.
    """
    engine_state = state or InsightEngineState()
    insights: list[dict[str, Any]] = []

    for item in insight_input.grip:
        if item.confidence < GRIP_CONFIDENCE_THRESHOLD:
            continue

        if item.track_evolution == TRACK_EVOLUTION_IMPROVING:
            _emit_insight(
                insights,
                category=INSIGHT_CATEGORY_GRIP,
                severity=SEVERITY_INFO,
                title="Grip improving",
                message=f"{item.segment_id} is gaining grip from clean samples.",
                confidence=item.confidence,
                segment_ids=(item.segment_id,),
                evidence={
                    "trackEvolution": _evidence_value(item.track_evolution, LABEL_INFERRED),
                    "gripIndex": _evidence_value(item.grip_index, LABEL_INFERRED),
                },
                now=now,
                state=engine_state,
                cooldown_seconds=cooldown_seconds,
                ttl_seconds=ttl_seconds,
            )
        elif item.track_evolution == TRACK_EVOLUTION_WORSENING:
            _emit_insight(
                insights,
                category=INSIGHT_CATEGORY_GRIP,
                severity=SEVERITY_WARNING,
                title="Grip worsening",
                message=f"{item.segment_id} grip is dropping versus recent clean samples.",
                confidence=item.confidence,
                segment_ids=(item.segment_id,),
                evidence={
                    "trackEvolution": _evidence_value(item.track_evolution, LABEL_INFERRED),
                    "gripIndex": _evidence_value(item.grip_index, LABEL_INFERRED),
                },
                now=now,
                state=engine_state,
                cooldown_seconds=cooldown_seconds,
                ttl_seconds=ttl_seconds,
            )

    for item in insight_input.traffic:
        if item.traffic_score < TRAFFIC_SCORE_THRESHOLD:
            continue

        _emit_insight(
            insights,
            category=INSIGHT_CATEGORY_TRAFFIC,
            severity=SEVERITY_WARNING,
            title="Traffic warning",
            message=f"Traffic pressure is high in {item.segment_id}.",
            confidence=0.9,
            segment_ids=(item.segment_id,),
            evidence={
                "trafficScore": _evidence_value(round(item.traffic_score, 1), LABEL_DERIVED),
            },
            now=now,
            state=engine_state,
            cooldown_seconds=cooldown_seconds,
            ttl_seconds=ttl_seconds,
        )

    for item in insight_input.wind:
        has_wind_class = item.wind_class not in (None, "", "unknown")
        is_high_wind = item.wind_speed_ms is not None and item.wind_speed_ms >= HIGH_WIND_SPEED_THRESHOLD_MS
        if not (has_wind_class and is_high_wind):
            continue

        _emit_insight(
            insights,
            category=INSIGHT_CATEGORY_WIND,
            severity=SEVERITY_WARNING,
            title="Wind watch",
            message=f"Strong {item.wind_class} detected in {item.segment_id}.",
            confidence=0.85,
            segment_ids=(item.segment_id,),
            evidence={
                "windSpeedMs": _evidence_value(item.wind_speed_ms, LABEL_MEASURED),
                "windClass": _evidence_value(item.wind_class, LABEL_DERIVED),
                "windStrengthScore": _evidence_value(item.wind_strength_score, LABEL_DERIVED),
            },
            now=now,
            state=engine_state,
            cooldown_seconds=cooldown_seconds,
            ttl_seconds=ttl_seconds,
        )

    for item in insight_input.dirty_zone:
        if item.probability < DIRTY_ZONE_PROBABILITY_THRESHOLD:
            continue

        _emit_insight(
            insights,
            category=INSIGHT_CATEGORY_DIRTY_ZONE,
            severity=SEVERITY_WARNING,
            title="Dirty-zone watch",
            message="Surface contamination risk is elevated in the highlighted segment(s).",
            confidence=item.confidence,
            segment_ids=item.segment_ids,
            evidence={
                "dirtyZoneProbability": _evidence_value(round(item.probability, 2), LABEL_INFERRED),
                "trigger": _evidence_value(item.trigger, LABEL_MEASURED),
            },
            now=now,
            state=engine_state,
            cooldown_seconds=cooldown_seconds,
            ttl_seconds=ttl_seconds,
        )

    for item in insight_input.tyre_stress:
        if item.stress_score < TYRE_STRESS_SCORE_THRESHOLD:
            continue

        _emit_insight(
            insights,
            category=INSIGHT_CATEGORY_TYRE_STRESS,
            severity=SEVERITY_WARNING,
            title="Tyre stress",
            message=f"Tyre stress is elevated in {item.segment_id}.",
            confidence=item.confidence,
            segment_ids=(item.segment_id,),
            evidence={
                "tyreStressScore": _evidence_value(round(item.stress_score, 1), LABEL_INFERRED),
                "stressLevel": _evidence_value(item.stress_level, LABEL_INFERRED),
            },
            now=now,
            state=engine_state,
            cooldown_seconds=cooldown_seconds,
            ttl_seconds=ttl_seconds,
        )

    for item in insight_input.rain:
        if item.probability < RAIN_INFLUENCE_PROBABILITY_THRESHOLD:
            continue

        _emit_insight(
            insights,
            category=INSIGHT_CATEGORY_RAIN,
            severity=SEVERITY_WARNING,
            title="Rain influence",
            message="Rain influence is likely affecting pace consistency.",
            confidence=item.confidence,
            segment_ids=item.segment_ids,
            evidence={
                "rainInfluenceProbability": _evidence_value(round(item.probability, 2), LABEL_INFERRED),
                "measuredRainfall": _evidence_value(item.measured_rainfall, LABEL_MEASURED),
            },
            now=now,
            state=engine_state,
            cooldown_seconds=cooldown_seconds,
            ttl_seconds=ttl_seconds,
        )

    return insights, engine_state
