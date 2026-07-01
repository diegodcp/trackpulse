from __future__ import annotations

from datetime import UTC, datetime, timedelta

from trackpulse_api.inference.grip import TRACK_EVOLUTION_IMPROVING, TRACK_EVOLUTION_WORSENING
from trackpulse_api.inference.insights import (
    DirtyZoneInsightInput,
    GripInsightInput,
    InsightEngineInput,
    RainInsightInput,
    TrafficInsightInput,
    TyreStressInsightInput,
    WindInsightInput,
    generate_rule_based_insights,
)


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_grip_improving_rule_emits_insight() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            grip=(
                GripInsightInput(
                    segment_id="s03",
                    track_evolution=TRACK_EVOLUTION_IMPROVING,
                    confidence=0.8,
                    grip_index=1.0,
                ),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    insight = insights[0]
    assert insight["category"] == "grip"
    assert insight["title"] == "Grip improving"
    assert insight["segmentIds"] == ["s03"]


def test_grip_worsening_rule_emits_insight() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            grip=(
                GripInsightInput(
                    segment_id="s05",
                    track_evolution=TRACK_EVOLUTION_WORSENING,
                    confidence=0.75,
                    grip_index=-1.0,
                ),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    assert insights[0]["title"] == "Grip worsening"


def test_traffic_rule_emits_warning_at_threshold() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            traffic=(
                TrafficInsightInput(segment_id="s04", traffic_score=70.0),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    assert insights[0]["category"] == "traffic"
    assert insights[0]["severity"] == "warning"


def test_wind_watch_rule_requires_high_speed_and_wind_class() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            wind=(
                WindInsightInput(segment_id="s01", wind_speed_ms=9.0, wind_class="headwind"),
                WindInsightInput(segment_id="s02", wind_speed_ms=6.0, wind_class="tailwind"),
                WindInsightInput(segment_id="s03", wind_speed_ms=9.0, wind_class="unknown"),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    assert insights[0]["category"] == "wind"
    assert insights[0]["segmentIds"] == ["s01"]


def test_dirty_zone_rule_emits_at_probability_threshold() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            dirty_zone=(
                DirtyZoneInsightInput(segment_ids=("s02", "s03"), probability=0.5, confidence=0.8),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    assert insights[0]["category"] == "dirty_zone"
    assert insights[0]["segmentIds"] == ["s02", "s03"]


def test_tyre_stress_rule_emits_at_score_threshold() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            tyre_stress=(
                TyreStressInsightInput(segment_id="s09", stress_score=70.0, confidence=0.82, stress_level="high"),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    assert insights[0]["category"] == "tyre_stress"


def test_rain_influence_rule_emits_at_probability_threshold() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            rain=(
                RainInsightInput(segment_ids=("s10",), probability=0.55, confidence=0.78, measured_rainfall=True),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    assert insights[0]["category"] == "rain"


def test_low_grip_confidence_emits_nothing() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            grip=(
                GripInsightInput(
                    segment_id="s06",
                    track_evolution=TRACK_EVOLUTION_IMPROVING,
                    confidence=0.69,
                    grip_index=1.0,
                ),
            ),
        ),
        now=_now(),
    )

    assert insights == []


def test_dedupe_cooldown_suppresses_repeat_then_allows_after_cooldown() -> None:
    now = _now()
    insight_input = InsightEngineInput(
        traffic=(
            TrafficInsightInput(segment_id="s11", traffic_score=88.0),
        ),
    )

    first_insights, state = generate_rule_based_insights(
        insight_input,
        now=now,
        cooldown_seconds=90.0,
    )
    second_insights, state = generate_rule_based_insights(
        insight_input,
        now=now + timedelta(seconds=20),
        state=state,
        cooldown_seconds=90.0,
    )
    third_insights, _ = generate_rule_based_insights(
        insight_input,
        now=now + timedelta(seconds=95),
        state=state,
        cooldown_seconds=90.0,
    )

    assert len(first_insights) == 1
    assert second_insights == []
    assert len(third_insights) == 1


def test_evidence_includes_truth_labels() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            wind=(
                WindInsightInput(
                    segment_id="s07",
                    wind_speed_ms=10.2,
                    wind_class="crosswind_right",
                    wind_strength_score=33.0,
                ),
            ),
            traffic=(
                TrafficInsightInput(segment_id="s07", traffic_score=73.0),
            ),
            grip=(
                GripInsightInput(
                    segment_id="s07",
                    track_evolution=TRACK_EVOLUTION_IMPROVING,
                    confidence=0.8,
                    grip_index=1.0,
                ),
            ),
        ),
        now=_now(),
    )

    by_category = {insight["category"]: insight for insight in insights}

    assert by_category["wind"]["evidence"]["windSpeedMs"]["label"] == "measured"
    assert by_category["wind"]["evidence"]["windClass"]["label"] == "derived"
    assert by_category["traffic"]["evidence"]["trafficScore"]["label"] == "derived"
    assert by_category["grip"]["evidence"]["trackEvolution"]["label"] == "inferred"


def test_every_insight_contains_required_fields() -> None:
    now = _now()
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            grip=(
                GripInsightInput(
                    segment_id="s01",
                    track_evolution=TRACK_EVOLUTION_IMPROVING,
                    confidence=0.8,
                ),
            ),
            traffic=(
                TrafficInsightInput(segment_id="s02", traffic_score=85.0),
            ),
            wind=(
                WindInsightInput(segment_id="s03", wind_speed_ms=9.0, wind_class="headwind"),
            ),
            dirty_zone=(
                DirtyZoneInsightInput(segment_ids=("s04",), probability=0.51, confidence=0.74),
            ),
            tyre_stress=(
                TyreStressInsightInput(segment_id="s05", stress_score=72.0, confidence=0.81),
            ),
            rain=(
                RainInsightInput(segment_ids=("s06",), probability=0.56, confidence=0.77),
            ),
        ),
        now=now,
    )

    required_fields = {
        "category",
        "severity",
        "title",
        "message",
        "confidence",
        "segmentIds",
        "evidence",
        "expiresAt",
    }

    assert len(insights) == 6
    for insight in insights:
        assert required_fields.issubset(insight.keys())
        assert insight["expiresAt"] > now.isoformat()
