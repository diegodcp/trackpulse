from __future__ import annotations

import asyncio
import importlib
import os
import uuid

import pytest

from trackpulse_api.replay.producer import KafkaReplayEventBus, ReplayStatus, ReplayStatusUpdate


@pytest.mark.asyncio
@pytest.mark.integration
async def test_kafka_replay_adapter_publishes_event_and_status_to_redpanda() -> None:
    bootstrap_servers = os.getenv("TRACKPULSE_KAFKA_BOOTSTRAP_SERVERS")
    if not bootstrap_servers:
        pytest.skip("Set TRACKPULSE_KAFKA_BOOTSTRAP_SERVERS to run Kafka replay adapter integration test")

    try:
        aiokafka = importlib.import_module("aiokafka")
    except ImportError:
        pytest.skip("aiokafka is required for Kafka replay adapter integration test")

    AIOKafkaProducer = getattr(aiokafka, "AIOKafkaProducer")
    AIOKafkaConsumer = getattr(aiokafka, "AIOKafkaConsumer")

    unique_suffix = uuid.uuid4().hex[:8]
    events_topic = f"trackpulse.replay.adapter.events.{unique_suffix}.v1"
    status_topic = f"trackpulse.replay.adapter.status.{unique_suffix}.v1"

    producer_client = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        client_id=f"trackpulse-replay-adapter-it-{unique_suffix}",
        acks="all",
    )
    consumer = AIOKafkaConsumer(
        events_topic,
        status_topic,
        bootstrap_servers=bootstrap_servers,
        group_id=f"trackpulse-replay-adapter-it-{unique_suffix}",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )

    await consumer.start()
    try:
        bus = KafkaReplayEventBus(producer_client, status_topic=status_topic)
        await bus.start()
        try:
            ack = await bus.publish_event(
                {
                    "event_id": "evt-it-001",
                    "fixture_id": "bahrain-2023-race",
                    "source": "openf1-fixture",
                    "topic": events_topic,
                    "event_type": "openf1.weather",
                    "occurred_at": "2023-03-05T15:00:00Z",
                    "payload": {"track_temperature": 41.9},
                }
            )
            await bus.publish_status(
                ReplayStatusUpdate(
                    fixture_id="bahrain-2023-race",
                    status=ReplayStatus.RUNNING,
                    speed_multiplier=20,
                    published_events=1,
                    total_events=1,
                    occurred_at="2023-03-05T15:00:00Z",
                    message="Replay event published",
                )
            )
        finally:
            await bus.close()

        first = await asyncio.wait_for(consumer.getone(), timeout=10)
        second = await asyncio.wait_for(consumer.getone(), timeout=10)

        assert ack.status == "ack"
        assert ack.topic == events_topic
        assert ack.offset is not None
        assert {first.topic, second.topic} == {events_topic, status_topic}
    finally:
        await consumer.stop()
