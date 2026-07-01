from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Callable, Protocol

from trackpulse_api.kafka import (
    RAW_OPENF1_CAR_DATA_TOPIC,
    RAW_OPENF1_LAPS_TOPIC,
    RAW_OPENF1_LOCATION_TOPIC,
    RAW_OPENF1_RACE_CONTROL_TOPIC,
    RAW_OPENF1_WEATHER_TOPIC,
    RawEventProducer,
    RawOpenF1Event,
)

from .token_manager import OpenF1TokenManager


MQTT_EVENT_TOPIC_MAP: dict[str, tuple[str, str]] = {
    "weather": (RAW_OPENF1_WEATHER_TOPIC, "openf1.weather"),
    "location": (RAW_OPENF1_LOCATION_TOPIC, "openf1.location"),
    "car_data": (RAW_OPENF1_CAR_DATA_TOPIC, "openf1.car_data"),
    "laps": (RAW_OPENF1_LAPS_TOPIC, "openf1.laps"),
    "race_control": (RAW_OPENF1_RACE_CONTROL_TOPIC, "openf1.race_control"),
}


class UnsupportedMqttTopicError(ValueError):
    pass


class MQTTMessage(Protocol):
    topic: str
    payload: bytes


class MQTTClient(Protocol):
    on_connect: Callable[[Any, Any, Any, int], None] | None
    on_message: Callable[[Any, Any, MQTTMessage], None] | None

    def username_pw_set(self, username: str | None = None, password: str | None = None) -> None:
        ...

    def tls_set(self, *args: Any, **kwargs: Any) -> None:
        ...

    def connect(self, host: str, port: int, keepalive: int = 60) -> None:
        ...

    def subscribe(self, topic: str) -> tuple[int, int]:
        ...

    def loop_forever(self) -> None:
        ...

    def disconnect(self) -> None:
        ...


class OpenF1LiveMqttConnector:
    def __init__(
        self,
        *,
        token_manager: OpenF1TokenManager,
        producer: RawEventProducer,
        mqtt_client_factory: Callable[[], MQTTClient],
        mqtt_host: str,
        mqtt_port: int,
        mqtt_topics: list[str],
        mqtt_username: str | None,
        reconnect_delay_seconds: float = 1.0,
    ) -> None:
        self._token_manager = token_manager
        self._producer = producer
        self._mqtt_client_factory = mqtt_client_factory
        self._mqtt_host = mqtt_host
        self._mqtt_port = mqtt_port
        self._mqtt_topics = mqtt_topics
        self._mqtt_username = mqtt_username
        self._reconnect_delay_seconds = reconnect_delay_seconds
        self._logger = logging.getLogger(__name__)
        self._loop: asyncio.AbstractEventLoop | None = None

    async def run(self, *, max_reconnect_attempts: int | None = None) -> None:
        self._loop = asyncio.get_running_loop()
        attempts = 0

        while True:
            if max_reconnect_attempts is not None and attempts >= max_reconnect_attempts:
                return

            client = self._mqtt_client_factory()
            client.on_connect = self._on_connect
            client.on_message = self._on_message

            try:
                token = await self._token_manager.get_token()
                client.username_pw_set(username=self._mqtt_username, password=token)
                client.tls_set()
                client.connect(self._mqtt_host, self._mqtt_port, keepalive=60)
                client.loop_forever()
                return
            except Exception:
                attempts += 1
                self._logger.warning("OpenF1 MQTT loop failed; reconnecting", exc_info=True)
                await asyncio.sleep(self._reconnect_delay_seconds)
            finally:
                try:
                    client.disconnect()
                except Exception:
                    self._logger.debug("OpenF1 MQTT disconnect raised and was ignored", exc_info=True)

    async def handle_message(self, topic: str, payload: bytes) -> None:
        event = self._build_raw_event(topic=topic, payload=payload)
        await self._producer.publish(event)

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        del userdata, flags
        if rc != 0:
            self._logger.warning("OpenF1 MQTT connected with non-zero return code rc=%s", rc)
            return

        for topic in self._mqtt_topics:
            client.subscribe(topic)

    def _on_message(self, client: Any, userdata: Any, msg: MQTTMessage) -> None:
        del client, userdata
        if self._loop is None:
            return

        future = asyncio.run_coroutine_threadsafe(
            self.handle_message(msg.topic, msg.payload),
            self._loop,
        )
        future.result()

    def _build_raw_event(self, *, topic: str, payload: bytes) -> RawOpenF1Event:
        try:
            message = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid MQTT message payload") from exc

        if not isinstance(message, dict):
            raise ValueError("MQTT message payload must be a JSON object")

        source_event_id = message.get("_id")
        source_key = message.get("_key")
        if source_event_id is None or source_key is None:
            raise ValueError("MQTT message payload must include _id and _key")

        raw_topic, event_type = resolve_mqtt_topic(topic)
        return RawOpenF1Event(
            event_id=str(source_event_id),
            source_id=str(source_key),
            fixture_id="live",
            source="openf1-live-mqtt",
            topic=raw_topic,
            event_type=event_type,
            payload=message,
            occurred_at=_coerce_optional_string(message.get("date")),
            session_key=_coerce_optional_int(message.get("session_key")),
            meeting_key=_coerce_optional_int(message.get("meeting_key")),
            driver_number=_coerce_optional_int(message.get("driver_number")),
            ingested_at=datetime.now(timezone.utc).isoformat(),
        )


def resolve_mqtt_topic(topic: str) -> tuple[str, str]:
    normalized = topic.strip().lower().strip("/")
    final_segment = normalized.split("/")[-1]
    if final_segment not in MQTT_EVENT_TOPIC_MAP:
        raise UnsupportedMqttTopicError(f"Unsupported MQTT topic: {topic}")
    return MQTT_EVENT_TOPIC_MAP[final_segment]


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_string(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None
