from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from trackpulse_api.inference.dirty_zone import (
    INFERRED_LABEL,
    TRIGGER_DOUBLE_YELLOW,
    TRIGGER_YELLOW,
    DirtyZoneInput,
    infer_dirty_zone_probability,
)


def test_yellow_sector_maps_to_segments() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = infer_dirty_zone_probability(
        DirtyZoneInput(
            event_time=now,
            sector=2,
            flag="yellow",
        ),
        {1: ["s01"], 2: ["s02a", "s02b"], 3: ["s03"]},
        now=now,
    )

    assert result.label == INFERRED_LABEL
    assert result.trigger == TRIGGER_YELLOW
    assert [segment.segment_id for segment in result.segments] == ["s02a", "s02b"]
    assert all(segment.probability == pytest.approx(0.35) for segment in result.segments)
    assert result.debris_confirmed is False


def test_double_yellow_is_higher_than_yellow() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    yellow = infer_dirty_zone_probability(
        DirtyZoneInput(event_time=now, sector=1, flag="yellow"),
        {1: ["s01"]},
        now=now,
    )
    double_yellow = infer_dirty_zone_probability(
        DirtyZoneInput(event_time=now, sector=1, flag="double yellow"),
        {1: ["s01"]},
        now=now,
    )

    assert yellow.trigger == TRIGGER_YELLOW
    assert double_yellow.trigger == TRIGGER_DOUBLE_YELLOW
    assert double_yellow.segments[0].probability > yellow.segments[0].probability


def test_debris_message_confirms_debris() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = infer_dirty_zone_probability(
        DirtyZoneInput(
            event_time=now,
            sector=3,
            message="Debris reported at turn 10",
        ),
        {3: ["s03"]},
        now=now,
    )

    assert result.debris_confirmed is True
    assert len(result.segments) == 1
    assert result.segments[0].probability == pytest.approx(0.75)


def test_probability_decays_over_time() -> None:
    event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    at_start = infer_dirty_zone_probability(
        DirtyZoneInput(event_time=event_time, sector=1, flag="yellow"),
        {1: ["s01"]},
        now=event_time,
    )
    later = infer_dirty_zone_probability(
        DirtyZoneInput(event_time=event_time, sector=1, flag="yellow"),
        {1: ["s01"]},
        now=event_time + timedelta(seconds=180),
    )

    assert later.segments[0].probability < at_start.segments[0].probability
    assert later.segments[0].probability > 0.0


def test_probability_expires() -> None:
    event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = infer_dirty_zone_probability(
        DirtyZoneInput(event_time=event_time, sector=2, flag="yellow"),
        {2: ["s02"]},
        now=event_time + timedelta(seconds=601),
        expiry_seconds=600.0,
    )

    assert result.segments == ()


def test_slowdown_confirmation_increases_confidence() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    without_confirmation = infer_dirty_zone_probability(
        DirtyZoneInput(event_time=now, sector=1, flag="yellow", slowdown_confirmed=False),
        {1: ["s01"]},
        now=now,
    )
    with_confirmation = infer_dirty_zone_probability(
        DirtyZoneInput(event_time=now, sector=1, flag="yellow", slowdown_confirmed=True),
        {1: ["s01"]},
        now=now,
    )

    assert with_confirmation.segments[0].confidence > without_confirmation.segments[0].confidence