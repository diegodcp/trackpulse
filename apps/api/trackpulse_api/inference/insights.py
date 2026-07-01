from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha1
from typing import Any

from pydantic import BaseModel, Field

HIGH_WIND_SPEED_THRESHOLD_MS = 8.0
SEGMENT_TREND_CONFIDENCE_THRESHOLD = 0.55
TRAFFIC_SCORE_THRESHOLD = 20.0
TRAFFIC_PERSISTENCE_UPDATES = 2
DIRTY_ZONE_PROBABILITY_THRESHOLD = 0.5

INSIGHT_CATEGORY_TRAFFIC = "traffic"
INSIGHT_CATEGORY_WIND = "wind"
INSIGHT_CATEGORY_DIRTY_ZONE = "dirty_zone"
INSIGHT_CATEGORY_SEGMENT_TREND = "segment_trend"

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"

LABEL_MEASURED = "measured"
LABEL_DERIVED = "derived"
LABEL_INFERRED = "inferred"


class InsightEvidence(BaseModel):
    value: Any
    truth_label: str


class LiveInsight(BaseModel):
    insight_id: str
    category: str
    severity: str
    title: str
    message: str
    affected_segment_ids: list[str] = Field(default_factory=list)
    confidence: float
    evidence: dict[str, InsightEvidence] = Field(default_factory=dict)
    truth_labels: list[str] = Field(default_factory=list)
    expires_at: datetime


@dataclass(frozen=True)
class TrafficInsightInput:
    segment_id: str
    traffic_score: float
    consecutive_updates: int = 1


@dataclass(frozen=True)
class WindInsightInput:
    segment_id: str
    wind_speed_ms: float | None
    wind_class: str | None
    wind_strength_score: float | None = None
    is_braking_zone: bool = False
    is_fast_corner: bool = False


@dataclass(frozen=True)
class DirtyZoneInsightInput:
    segment_ids: tuple[str, ...]
    probability: float
    confidence: float
    trigger: str | None = None


@dataclass(frozen=True)
class SegmentTrendInsightInput:
    segment_id: str
    avg_speed_delta_kmh: float
    confidence: float
    clean_sample_count: int


@dataclass(frozen=True)
class InsightEngineInput:
    traffic: tuple[TrafficInsightInput, ...] = ()
    wind: tuple[WindInsightInput, ...] = ()
    segment_trend: tuple[SegmentTrendInsightInput, ...] = ()
    dirty_zone: tuple[DirtyZoneInsightInput, ...] = ()


@dataclass(frozen=True)
class InsightEngineState:
    last_emitted_at: dict[str, datetime] = field(default_factory=dict)


def _evidence_value(value: Any, label: str) -> InsightEvidence:
    return InsightEvidence(value=value, truth_label=label)


def _deterministic_insight_id(category: str, title: str, segment_ids: tuple[str, ...]) -> str:
    stable_segments = ",".join(sorted(segment_ids))
    digest = sha1(f"{category}|{title}|{stable_segments}".encode("utf-8")).hexdigest()
    return f"li-{digest[:16]}"


def _insight_payload(
    *,
    category: str,
    severity: str,
    title: str,
    message: str,
    confidence: float,
    segment_ids: tuple[str, ...],
    evidence: dict[str, InsightEvidence],
    expires_at: datetime,
) -> LiveInsight:
    truth_labels = sorted({item.truth_label for item in evidence.values()})
    return LiveInsight(
        insight_id=_deterministic_insight_id(category, title, segment_ids),
        category=category,
        severity=severity,
        title=title,
        message=message,
        confidence=round(max(0.0, min(1.0, confidence)), 2),
        affected_segment_ids=list(segment_ids),
        evidence=evidence,
        truth_labels=truth_labels,
        expires_at=expires_at,
    )


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
    insights: list[LiveInsight],
    *,
    category: str,
    severity: str,
    title: str,
    message: str,
    confidence: float,
    segment_ids: tuple[str, ...],
    evidence: dict[str, InsightEvidence],
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
) -> tuple[list[LiveInsight], InsightEngineState]:
    """Generate TP-BH-0019 rule-based live insights."""
    engine_state = state or InsightEngineState()
    insights: list[LiveInsight] = []

    for item in insight_input.traffic:
        if item.traffic_score < TRAFFIC_SCORE_THRESHOLD or item.consecutive_updates < TRAFFIC_PERSISTENCE_UPDATES:
            continue

        _emit_insight(
            insights,
            category=INSIGHT_CATEGORY_TRAFFIC,
            severity=SEVERITY_WARNING,
            title="Traffic cluster persists",
            message=f"Cars are continuing to bunch through {item.segment_id}, so pace there could stay compromised.",
            confidence=min(0.95, round(0.55 + (item.traffic_score / 100.0) * 0.4, 2)),
            segment_ids=(item.segment_id,),
            evidence={
                "traffic_score": _evidence_value(round(item.traffic_score, 1), LABEL_DERIVED),
                "consecutive_updates": _evidence_value(item.consecutive_updates, LABEL_DERIVED),
            },
            now=now,
            state=engine_state,
            cooldown_seconds=cooldown_seconds,
            ttl_seconds=ttl_seconds,
        )

    for item in insight_input.wind:
        has_wind_class = item.wind_class not in (None, "", "unknown")
        is_high_wind = item.wind_speed_ms is not None and item.wind_speed_ms >= HIGH_WIND_SPEED_THRESHOLD_MS
        targets_sensitive_corner = item.is_braking_zone or item.is_fast_corner
        if not (has_wind_class and is_high_wind and targets_sensitive_corner):
            continue

        if item.is_braking_zone and item.is_fast_corner:
            segment_context = "braking-heavy fast corner"
        elif item.is_braking_zone:
            segment_context = "braking zone"
        else:
            segment_context = "fast corner"

        _emit_insight(
            insights,
            category=INSIGHT_CATEGORY_WIND,
            severity=SEVERITY_WARNING,
            title="Strong wind at corner entry",
            message=f"Strong {item.wind_class} could affect the {segment_context} around {item.segment_id}.",
            confidence=0.85,
            segment_ids=(item.segment_id,),
            evidence={
                "wind_speed_ms": _evidence_value(item.wind_speed_ms, LABEL_MEASURED),
                "wind_class": _evidence_value(item.wind_class, LABEL_DERIVED),
                "wind_strength_score": _evidence_value(item.wind_strength_score, LABEL_DERIVED),
            },
            now=now,
            state=engine_state,
            cooldown_seconds=cooldown_seconds,
            ttl_seconds=ttl_seconds,
        )

    for item in insight_input.segment_trend:
        if item.confidence < SEGMENT_TREND_CONFIDENCE_THRESHOLD:
            continue
        if item.avg_speed_delta_kmh <= 0.0:
            continue

        _emit_insight(
            insights,
            category=INSIGHT_CATEGORY_SEGMENT_TREND,
            severity=SEVERITY_INFO,
            title="Segment trending faster",
            message=f"{item.segment_id} is trending faster from recent clean speed samples.",
            confidence=item.confidence,
            segment_ids=(item.segment_id,),
            evidence={
                "avg_speed_delta_kmh": _evidence_value(round(item.avg_speed_delta_kmh, 2), LABEL_INFERRED),
                "clean_sample_count": _evidence_value(item.clean_sample_count, LABEL_INFERRED),
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
            title="Dirty-zone placeholder",
            message="Race-control context suggests a possible contamination zone in the highlighted segment(s).",
            confidence=item.confidence,
            segment_ids=item.segment_ids,
            evidence={
                "dirty_zone_probability": _evidence_value(round(item.probability, 2), LABEL_INFERRED),
                "trigger": _evidence_value(item.trigger, LABEL_MEASURED),
            },
            now=now,
            state=engine_state,
            cooldown_seconds=cooldown_seconds,
            ttl_seconds=ttl_seconds,
        )

    return insights, engine_state
