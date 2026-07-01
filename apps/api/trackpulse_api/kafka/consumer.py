from __future__ import annotations

from typing import Any, Protocol

from .models import InvalidRawOpenF1EventError, RawOpenF1Event


class KafkaConsumerMessage(Protocol):
    topic: str
    value: bytes


class KafkaConsumerClient(Protocol):
    async def getone(self) -> Any:
        ...


class KafkaRawEventConsumer:
    """Read and validate raw OpenF1 events from a Kafka-compatible consumer."""

    def __init__(self, client: KafkaConsumerClient) -> None:
        self._client = client

    async def get_event(self) -> RawOpenF1Event:
        message: KafkaConsumerMessage = await self._client.getone()
        try:
            return RawOpenF1Event.from_message_bytes(message.value)
        except InvalidRawOpenF1EventError as exc:
            raise InvalidRawOpenF1EventError(
                f"Invalid message received on topic {message.topic}"
            ) from exc

    async def close(self) -> None:
        stop = getattr(self._client, "stop", None)
        if callable(stop):
            await stop()
