from __future__ import annotations

import asyncio
import importlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import logging
from typing import Any, Awaitable, Callable, Protocol

from .topics import REPLAY_DEFAULT_EVENT_TOPIC, REPLAY_STATUS_TOPIC

logger = logging.getLogger(__name__)

ReplaySubscriber = Callable[[dict[str, Any]], None | Awaitable[None]]
StatusSubscriber = Callable[["ReplayStatusUpdate"], None | Awaitable[None]]

SUPPORTED_SPEED_MULTIPLIERS: frozenset[int] = frozenset({1, 5, 10, 20, 100})


class ReplayStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ReplayStatusUpdate:
    fixture_id: str
    status: ReplayStatus
    speed_multiplier: int
    published_events: int
    total_events: int
    occurred_at: str | None
    message: str


@dataclass(frozen=True)
class ReplayPublishAck:
    topic: str
    partition: int | None
    offset: int | None
    status: str


class ReplayEventPublisher(Protocol):
    async def start(self) -> None:
        ...

    async def publish_event(self, event: dict[str, Any]) -> ReplayPublishAck:
        ...

    async def publish_status(self, status_update: ReplayStatusUpdate) -> None:
        ...

    async def close(self) -> None:
        ...


class InMemoryEventBus:
    """Simple in-memory pub/sub bus for replay tests and local integration."""

    def __init__(self) -> None:
        self._event_subscribers: list[ReplaySubscriber] = []
        self._status_subscribers: list[StatusSubscriber] = []
        self.published_events: list[dict[str, Any]] = []
        self.status_updates: list[ReplayStatusUpdate] = []

    async def start(self) -> None:
        return None

    def subscribe_events(self, subscriber: ReplaySubscriber) -> None:
        self._event_subscribers.append(subscriber)

    def subscribe_status(self, subscriber: StatusSubscriber) -> None:
        self._status_subscribers.append(subscriber)

    async def publish_event(self, event: dict[str, Any]) -> ReplayPublishAck:
        self.published_events.append(event)
        for subscriber in self._event_subscribers:
            result = subscriber(event)
            if asyncio.iscoroutine(result):
                await result

        return ReplayPublishAck(
            topic=str(event.get("topic") or REPLAY_DEFAULT_EVENT_TOPIC),
            partition=None,
            offset=len(self.published_events) - 1,
            status="memory",
        )

    async def publish_status(self, status_update: ReplayStatusUpdate) -> None:
        self.status_updates.append(status_update)
        for subscriber in self._status_subscribers:
            result = subscriber(status_update)
            if asyncio.iscoroutine(result):
                await result

    async def close(self) -> None:
        return None


class KafkaProducerClient(Protocol):
    async def send_and_wait(
        self,
        topic: str,
        value: bytes,
        key: bytes | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> Any:
        ...


class KafkaReplayEventBus:
    """Publish replay events/status updates to Kafka-compatible brokers."""

    def __init__(
        self,
        client: KafkaProducerClient,
        *,
        status_topic: str = REPLAY_STATUS_TOPIC,
    ) -> None:
        self._client = client
        self._status_topic = status_topic
        self._started = False

    async def start(self) -> None:
        if self._started:
            return

        start = getattr(self._client, "start", None)
        if callable(start):
            await start()
        self._started = True

    async def publish_event(self, event: dict[str, Any]) -> ReplayPublishAck:
        topic = str(event.get("topic") or REPLAY_DEFAULT_EVENT_TOPIC)
        key = _event_key(event)
        event_type = event.get("event_type")
        headers = None
        if isinstance(event_type, str) and event_type:
            headers = [("event_type", event_type.encode("utf-8"))]

        payload = json.dumps(event, separators=(",", ":"), sort_keys=True).encode("utf-8")
        metadata = await self._client.send_and_wait(
            topic=topic,
            value=payload,
            key=key,
            headers=headers,
        )
        return ReplayPublishAck(
            topic=str(getattr(metadata, "topic", topic)),
            partition=getattr(metadata, "partition", None),
            offset=getattr(metadata, "offset", None),
            status="ack",
        )

    async def publish_status(self, status_update: ReplayStatusUpdate) -> None:
        payload = {
            "fixture_id": status_update.fixture_id,
            "status": status_update.status.value,
            "speed_multiplier": status_update.speed_multiplier,
            "published_events": status_update.published_events,
            "total_events": status_update.total_events,
            "occurred_at": status_update.occurred_at,
            "message": status_update.message,
        }
        await self._client.send_and_wait(
            topic=self._status_topic,
            value=json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
            key=status_update.fixture_id.encode("utf-8"),
        )

    async def close(self) -> None:
        stop = getattr(self._client, "stop", None)
        if callable(stop):
            await stop()
        self._started = False


def build_replay_event_bus(
    *,
    mode: str = "memory",
    kafka_bootstrap_servers: str = "localhost:9092",
    kafka_client_id: str = "trackpulse-replay-producer",
    kafka_acks: str = "all",
    kafka_status_topic: str = REPLAY_STATUS_TOPIC,
    kafka_client_factory: Callable[..., KafkaProducerClient] | None = None,
) -> ReplayEventPublisher:
    if mode == "memory":
        return InMemoryEventBus()

    if mode != "kafka":
        raise ValueError("mode must be either 'memory' or 'kafka'")

    client_factory = kafka_client_factory or _default_aiokafka_client_factory
    client = client_factory(
        bootstrap_servers=kafka_bootstrap_servers,
        client_id=kafka_client_id,
        acks=kafka_acks,
    )
    return KafkaReplayEventBus(client, status_topic=kafka_status_topic)


def _default_aiokafka_client_factory(*, bootstrap_servers: str, client_id: str, acks: str) -> KafkaProducerClient:
    try:
        aiokafka = importlib.import_module("aiokafka")
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "aiokafka is required for Kafka replay producer mode. Install with: pip install aiokafka"
        ) from exc

    AIOKafkaProducer = getattr(aiokafka, "AIOKafkaProducer")
    return AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        client_id=client_id,
        acks=acks,
    )


def _event_key(event: dict[str, Any]) -> bytes | None:
    event_id = event.get("event_id")
    if isinstance(event_id, str) and event_id:
        return event_id.encode("utf-8")

    fixture_id = event.get("fixture_id")
    if isinstance(fixture_id, str) and fixture_id:
        return fixture_id.encode("utf-8")

    return None


class FixtureReplayProducer:
    """Replay normalized NDJSON events over an in-memory bus.

    Ordering is deterministic because events are published in NDJSON file order.
    Replay pacing is based on consecutive occurred_at timestamps and the selected
    speed multiplier.
    """

    def __init__(
        self,
        *,
        fixture_id: str,
        events_path: Path,
        event_bus: ReplayEventPublisher,
        speed_multiplier: int = 1,
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if speed_multiplier not in SUPPORTED_SPEED_MULTIPLIERS:
            raise ValueError(
                "speed_multiplier must be one of "
                f"{sorted(SUPPORTED_SPEED_MULTIPLIERS)}"
            )

        self.fixture_id = fixture_id
        self.events_path = events_path
        self.event_bus = event_bus
        self.speed_multiplier = speed_multiplier
        self._sleep = sleep_fn

        self._events: list[dict[str, Any]] = []
        self._state: ReplayStatus = ReplayStatus.IDLE
        self._published_events = 0

        self._pause_gate = asyncio.Event()
        self._pause_gate.set()
        self._stop_requested = False
        self._task: asyncio.Task[None] | None = None

    @property
    def state(self) -> ReplayStatus:
        return self._state

    @property
    def total_events(self) -> int:
        return len(self._events)

    @property
    def published_events(self) -> int:
        return self._published_events

    def set_speed_multiplier(self, speed_multiplier: int) -> None:
        if speed_multiplier not in SUPPORTED_SPEED_MULTIPLIERS:
            raise ValueError(
                "speed_multiplier must be one of "
                f"{sorted(SUPPORTED_SPEED_MULTIPLIERS)}"
            )
        self.speed_multiplier = speed_multiplier

    async def start(self) -> bool:
        if self._task is not None and not self._task.done():
            return False

        await self.event_bus.start()
        self._events = _load_ndjson_events(self.events_path)
        self._published_events = 0
        self._stop_requested = False
        self._pause_gate.set()
        self._state = ReplayStatus.RUNNING
        await self._emit_status(message="Replay started", occurred_at=None)

        self._task = asyncio.create_task(self._run())
        return True

    async def pause(self) -> bool:
        if self._state is not ReplayStatus.RUNNING:
            return False

        self._pause_gate.clear()
        self._state = ReplayStatus.PAUSED
        await self._emit_status(message="Replay paused", occurred_at=None)
        return True

    async def resume(self) -> bool:
        if self._state is not ReplayStatus.PAUSED:
            return False

        self._pause_gate.set()
        self._state = ReplayStatus.RUNNING
        await self._emit_status(message="Replay resumed", occurred_at=None)
        return True

    async def stop(self) -> bool:
        if self._state in {ReplayStatus.STOPPED, ReplayStatus.COMPLETED, ReplayStatus.IDLE}:
            return False

        self._stop_requested = True
        self._pause_gate.set()

        if self._task is not None:
            await self._task

        return True

    async def wait(self) -> None:
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        previous_occurred_at_seconds: float | None = None

        try:
            for event in self._events:
                if self._stop_requested:
                    self._state = ReplayStatus.STOPPED
                    await self._emit_status(message="Replay stopped", occurred_at=None)
                    return

                await self._pause_gate.wait()
                if self._stop_requested:
                    self._state = ReplayStatus.STOPPED
                    await self._emit_status(message="Replay stopped", occurred_at=None)
                    return

                occurred_at = _parse_timestamp_seconds(event.get("occurred_at"))
                if previous_occurred_at_seconds is not None and occurred_at is not None:
                    delay_seconds = max(0.0, (occurred_at - previous_occurred_at_seconds) / self.speed_multiplier)
                    if delay_seconds > 0:
                        await self._sleep(delay_seconds)
                else:
                    await self._sleep(0)

                await self._pause_gate.wait()
                if self._stop_requested:
                    self._state = ReplayStatus.STOPPED
                    await self._emit_status(message="Replay stopped", occurred_at=None)
                    return

                publish_ack = await self.event_bus.publish_event(event)
                self._published_events += 1
                logger.info(
                    "Replay publish ack topic=%s partition=%s offset=%s ack_status=%s event_count=%s",
                    publish_ack.topic,
                    publish_ack.partition,
                    publish_ack.offset,
                    publish_ack.status,
                    self._published_events,
                )
                await self._emit_status(
                    message="Replay event published",
                    occurred_at=event.get("occurred_at"),
                )

                if occurred_at is not None:
                    previous_occurred_at_seconds = occurred_at

            self._state = ReplayStatus.COMPLETED
            await self._emit_status(message="Replay completed", occurred_at=None)
        finally:
            self._task = None

    async def _emit_status(self, *, message: str, occurred_at: str | None) -> None:
        await self.event_bus.publish_status(
            ReplayStatusUpdate(
                fixture_id=self.fixture_id,
                status=self._state,
                speed_multiplier=self.speed_multiplier,
                published_events=self._published_events,
                total_events=len(self._events),
                occurred_at=occurred_at,
                message=message,
            )
        )


def _parse_timestamp_seconds(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.timestamp()


def _load_ndjson_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Replay events file not found: {path}")

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise ValueError(
                    f"Expected object on line {line_number} in {path}, got {type(parsed).__name__}"
                )
            events.append(parsed)

    return events
