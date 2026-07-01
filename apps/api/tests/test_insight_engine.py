from __future__ import annotations

from datetime import UTC, datetime, timedelta

from trackpulse_api.inference.insights import (
    DirtyZoneInsightInput,
    InsightEngineInput,
    SegmentTrendInsightInput,
    TrafficInsightInput,
    WindInsightInput,
    generate_rule_based_insights,
)


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_strong_wind_rule_targets_sensitive_segment() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            wind=(
                WindInsightInput(
                    segment_id="bh-s01",
                    wind_speed_ms=9.2,
                    wind_class="headwind",
                    wind_strength_score=45.0,
                    is_braking_zone=True,
                ),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    assert insights[0].category == "wind"
    assert insights[0].title == "Strong wind at corner entry"
    assert insights[0].affected_segment_ids == ["bh-s01"]


def test_traffic_cluster_rule_requires_persistence() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            traffic=(
                TrafficInsightInput(segment_id="bh-s08", traffic_score=40.0, consecutive_updates=2),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    assert insights[0].title == "Traffic cluster persists"


def test_segment_trending_faster_rule_emits_insight() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            segment_trend=(
                SegmentTrendInsightInput(
                    segment_id="bh-s06",
                    avg_speed_delta_kmh=1.8,
                    confidence=0.72,
                    clean_sample_count=6,
                ),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    assert insights[0].category == "segment_trend"
    assert insights[0].title == "Segment trending faster"


def test_dirty_zone_placeholder_rule_emits_for_sector_backed_event() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            dirty_zone=(
                DirtyZoneInsightInput(
                    segment_ids=("bh-s11", "bh-s12"),
                    probability=0.75,
                    confidence=0.7,
                    trigger="debris_message",
                ),
            ),
        ),
        now=_now(),
    )

    assert len(insights) == 1
    assert insights[0].category == "dirty_zone"
    assert insights[0].title == "Dirty-zone placeholder"


def test_ids_are_deterministic_for_same_rule_key() -> None:
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            traffic=(
                TrafficInsightInput(segment_id="bh-s08", traffic_score=40.0, consecutive_updates=2),
            ),
        ),
        now=_now(),
    )
    repeated, _ = generate_rule_based_insights(
        InsightEngineInput(
            traffic=(
                TrafficInsightInput(segment_id="bh-s08", traffic_score=41.0, consecutive_updates=2),
            ),
        ),
        now=_now() + timedelta(seconds=91),
    )

    assert insights[0].insight_id == repeated[0].insight_id


def test_dedupe_cooldown_suppresses_repeat_then_allows_after_cooldown() -> None:
    now = _now()
    insight_input = InsightEngineInput(
        traffic=(
            TrafficInsightInput(segment_id="bh-s11", traffic_score=40.0, consecutive_updates=2),
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
                    segment_id="bh-s07",
                    wind_speed_ms=10.2,
                    wind_class="crosswind_right",
                    wind_strength_score=33.0,
                    is_fast_corner=True,
                ),
            ),
            traffic=(
                TrafficInsightInput(segment_id="bh-s07", traffic_score=32.0, consecutive_updates=2),
            ),
        ),
        now=_now(),
    )

    by_category = {insight.category: insight for insight in insights}

    assert by_category["wind"].evidence["wind_speed_ms"].truth_label == "measured"
    assert by_category["wind"].evidence["wind_class"].truth_label == "derived"
    assert by_category["traffic"].evidence["traffic_score"].truth_label == "derived"
    assert by_category["wind"].truth_labels == ["derived", "measured"]


def test_every_insight_contains_required_fields() -> None:
    now = _now()
    insights, _ = generate_rule_based_insights(
        InsightEngineInput(
            traffic=(
                TrafficInsightInput(segment_id="bh-s02", traffic_score=40.0, consecutive_updates=2),
            ),
            wind=(
                WindInsightInput(
                    segment_id="bh-s03",
                    wind_speed_ms=9.0,
                    wind_class="headwind",
                    is_fast_corner=True,
                ),
            ),
            segment_trend=(
                SegmentTrendInsightInput(
                    segment_id="bh-s06",
                    avg_speed_delta_kmh=1.1,
                    confidence=0.7,
                    clean_sample_count=6,
                ),
            ),
            dirty_zone=(
                DirtyZoneInsightInput(segment_ids=("bh-s04",), probability=0.51, confidence=0.74),
            ),
        ),
        now=now,
    )

    required_fields = {
        "insight_id",
        "category",
        "severity",
        "title",
        "message",
        "confidence",
        "affected_segment_ids",
        "evidence",
        "truth_labels",
        "expires_at",
    }

    assert len(insights) == 4
    for insight in insights:
        payload = insight.model_dump()
        assert required_fields.issubset(payload.keys())
        assert insight.expires_at > now
