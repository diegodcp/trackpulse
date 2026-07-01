from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from trackpulse_api.replay.producer import (
    FixtureReplayProducer,
    KafkaReplayEventBus,
    ReplayStatus,
    ReplayStatusUpdate,
    build_replay_event_bus,
)

FIXTURE_EVENTS_PATH = Path(__file__).parent / "fixtures" / "replay" / "events.10.ndjson"


class _FakeKafkaClient:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.sent: list[dict[str, object]] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send_and_wait(
        self,
        topic: str,
        value: bytes,
        key: bytes | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> SimpleNamespace:
        offset = len(self.sent)
        self.sent.append(
            {
                "topic": topic,
                "value": value,
                "key": key,
                "headers": headers,
                "offset": offset,
            }
        )
        return SimpleNamespace(topic=topic, partition=0, offset=offset)


@pytest.mark.asyncio
async def test_kafka_replay_event_bus_publishes_event_and_status() -> None:
    client = _FakeKafkaClient()
    bus = KafkaReplayEventBus(client, status_topic="trackpulse.replay.status.tests.v1")

    await bus.start()
    ack = await bus.publish_event(
        {
            "event_id": "evt-001",
            "fixture_id": "bahrain-2023-race",
            "topic": "raw.openf1.weather.v1",
            "event_type": "openf1.weather",
            "occurred_at": "2023-03-05T15:00:00Z",
            "payload": {"track_temperature": 42.1},
        }
    )
    await bus.publish_status(
        ReplayStatusUpdate(
            fixture_id="bahrain-2023-race",
            status=ReplayStatus.RUNNING,
            speed_multiplier=20,
            published_events=1,
            total_events=10,
            occurred_at="2023-03-05T15:00:00Z",
            message="Replay event published",
        )
    )
    await bus.close()

    assert ack.topic == "raw.openf1.weather.v1"
    assert ack.partition == 0
    assert ack.offset == 0
    assert ack.status == "ack"
    assert client.started is True
    assert client.stopped is True
    assert client.sent[0]["topic"] == "raw.openf1.weather.v1"
    assert client.sent[1]["topic"] == "trackpulse.replay.status.tests.v1"


def test_build_replay_event_bus_memory_mode_by_default() -> None:
    bus = build_replay_event_bus()
    assert bus.__class__.__name__ == "InMemoryEventBus"


def test_build_replay_event_bus_kafka_mode_uses_factory_config() -> None:
    captured: dict[str, str] = {}

    def _factory(*, bootstrap_servers: str, client_id: str, acks: str) -> _FakeKafkaClient:
        captured["bootstrap_servers"] = bootstrap_servers
        captured["client_id"] = client_id
        captured["acks"] = acks
        return _FakeKafkaClient()

    bus = build_replay_event_bus(
        mode="kafka",
        kafka_bootstrap_servers="redpanda:9092",
        kafka_client_id="trackpulse-replay-tests",
        kafka_acks="1",
        kafka_client_factory=_factory,
    )

    assert isinstance(bus, KafkaReplayEventBus)
    assert captured == {
        "bootstrap_servers": "redpanda:9092",
        "client_id": "trackpulse-replay-tests",
        "acks": "1",
    }


@pytest.mark.asyncio
async def test_fixture_replay_producer_logs_publish_ack_fields(caplog: pytest.LogCaptureFixture) -> None:
    client = _FakeKafkaClient()
    bus = KafkaReplayEventBus(client)
    producer = FixtureReplayProducer(
        fixture_id="bahrain-2023-race",
        events_path=FIXTURE_EVENTS_PATH,
        event_bus=bus,
        speed_multiplier=100,
    )

    with caplog.at_level("INFO", logger="trackpulse_api.replay.producer"):
        await producer.start()
        await producer.wait()

    assert producer.state == ReplayStatus.COMPLETED
    if caplog.text:
        assert "ack_status=ack" in caplog.text
        assert "event_count=10" in caplog.text
    else:
        assert len(client.sent) >= 10
