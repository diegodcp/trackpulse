from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from trackpulse_api.kafka import (
    InMemoryRawEventProducer,
    InvalidRawOpenF1EventError,
    KafkaRawEventConsumer,
    RawOpenF1Event,
    RAW_OPENF1_WEATHER_TOPIC,
)
from workers.fixtures.replay_to_kafka import replay_fixture_events


def test_raw_openf1_event_serializes_and_deserializes() -> None:
    event = RawOpenF1Event(
        event_id="evt-001",
        fixture_id="bahrain-2023-race",
        source="openf1-fixture",
        topic=RAW_OPENF1_WEATHER_TOPIC,
        event_type="openf1.weather",
        occurred_at="2023-03-05T15:00:00Z",
        payload={"track_temperature": 42.1},
    )

    serialized = event.to_message_bytes()
    deserialized = RawOpenF1Event.from_message_bytes(serialized)

    assert deserialized == event


@pytest.mark.asyncio
async def test_consumer_invalid_message_raises_controlled_error() -> None:
    class _FakeConsumer:
        async def getone(self) -> SimpleNamespace:
            return SimpleNamespace(topic=RAW_OPENF1_WEATHER_TOPIC, value=b"not-json")

    consumer = KafkaRawEventConsumer(_FakeConsumer())

    with pytest.raises(InvalidRawOpenF1EventError, match="Invalid message received"):
        await consumer.get_event()


@pytest.mark.asyncio
async def test_fixture_replay_produces_events(tmp_path: Path) -> None:
    events_path = tmp_path / "events.ndjson"
    events_path.write_text(
        "\n".join(
            [
                '{"event_id":"evt-001","fixture_id":"bahrain-2023-race","source":"openf1-fixture","topic":"raw.openf1.weather.v1","event_type":"openf1.weather","occurred_at":"2023-03-05T15:00:00Z","payload":{"track_temperature":41.2}}',
                '{"event_id":"evt-002","fixture_id":"bahrain-2023-race","source":"openf1-fixture","topic":"raw.openf1.weather.v1","event_type":"openf1.weather","occurred_at":"2023-03-05T15:01:00Z","payload":{"track_temperature":41.4}}',
            ]
        ),
        encoding="utf-8",
    )

    producer = InMemoryRawEventProducer()
    published_count = await replay_fixture_events(events_path=events_path, producer=producer)

    assert published_count == 2
    assert [event.event_id for event in producer.events] == ["evt-001", "evt-002"]
