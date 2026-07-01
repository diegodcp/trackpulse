from __future__ import annotations

import asyncio
from pathlib import Path
from time import perf_counter

import pytest

from trackpulse_api.replay import FixtureReplayProducer, InMemoryEventBus, ReplayStatus


FIXTURE_EVENTS_PATH = Path(__file__).parent / "fixtures" / "replay" / "events.10.ndjson"


@pytest.mark.asyncio
async def test_replay_producer_publishes_events_in_deterministic_order() -> None:
    bus = InMemoryEventBus()
    producer = FixtureReplayProducer(
        fixture_id="bahrain-2023-race",
        events_path=FIXTURE_EVENTS_PATH,
        event_bus=bus,
        speed_multiplier=100,
    )

    started = await producer.start()
    await producer.wait()

    assert started is True
    assert producer.state == ReplayStatus.COMPLETED
    assert len(bus.published_events) == 10
    assert [event["event_id"] for event in bus.published_events] == [
        "evt-001",
        "evt-002",
        "evt-003",
        "evt-004",
        "evt-005",
        "evt-006",
        "evt-007",
        "evt-008",
        "evt-009",
        "evt-010",
    ]

    assert bus.status_updates[0].status == ReplayStatus.RUNNING
    assert bus.status_updates[-1].status == ReplayStatus.COMPLETED


@pytest.mark.asyncio
async def test_replay_producer_pause_and_resume() -> None:
    bus = InMemoryEventBus()
    producer = FixtureReplayProducer(
        fixture_id="bahrain-2023-race",
        events_path=FIXTURE_EVENTS_PATH,
        event_bus=bus,
        speed_multiplier=20,
    )

    await producer.start()
    await asyncio.sleep(0.08)

    paused = await producer.pause()
    paused_count = len(bus.published_events)
    await asyncio.sleep(0.12)

    assert paused is True
    assert producer.state == ReplayStatus.PAUSED
    assert len(bus.published_events) == paused_count

    resumed = await producer.resume()
    await producer.wait()

    assert resumed is True
    assert producer.state == ReplayStatus.COMPLETED
    assert len(bus.published_events) == 10
    assert any(update.status == ReplayStatus.PAUSED for update in bus.status_updates)


@pytest.mark.asyncio
async def test_replay_producer_100x_completes_quickly() -> None:
    bus = InMemoryEventBus()
    producer = FixtureReplayProducer(
        fixture_id="bahrain-2023-race",
        events_path=FIXTURE_EVENTS_PATH,
        event_bus=bus,
        speed_multiplier=100,
    )

    started_at = perf_counter()
    await producer.start()
    await producer.wait()
    elapsed = perf_counter() - started_at

    assert producer.state == ReplayStatus.COMPLETED
    assert len(bus.published_events) == 10
    assert elapsed < 0.5
