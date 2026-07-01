from __future__ import annotations

from typing import Any, Protocol

from .models import RawOpenF1Event


class RawEventProducer(Protocol):
    async def publish(self, event: RawOpenF1Event) -> None:
        ...

    async def close(self) -> None:
        ...


class KafkaProducerClient(Protocol):
    async def send_and_wait(
        self,
        topic: str,
        value: bytes,
        key: bytes | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> Any:
        ...


class KafkaRawEventProducer:
    """Publish RawOpenF1Event payloads to Kafka-compatible brokers."""

    def __init__(self, client: KafkaProducerClient) -> None:
        self._client = client

    async def publish(self, event: RawOpenF1Event) -> None:
        key = event.source_id or event.event_id
        await self._client.send_and_wait(
            topic=event.topic,
            value=event.to_message_bytes(),
            key=key.encode("utf-8"),
            headers=[("event_type", event.event_type.encode("utf-8"))],
        )

    async def close(self) -> None:
        stop = getattr(self._client, "stop", None)
        if callable(stop):
            await stop()


class InMemoryRawEventProducer:
    """Testing producer that records published events in-memory."""

    def __init__(self) -> None:
        self.events: list[RawOpenF1Event] = []

    async def publish(self, event: RawOpenF1Event) -> None:
        self.events.append(event)

    async def close(self) -> None:
        return None
