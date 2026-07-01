from __future__ import annotations

import logging

import httpx
import pytest

from trackpulse_api.kafka import InMemoryRawEventProducer, RAW_OPENF1_WEATHER_TOPIC
from trackpulse_api.openf1.live_mqtt import OpenF1LiveMqttConnector
from trackpulse_api.openf1.token_manager import OpenF1TokenManager


class _FakeTokenManager:
    def __init__(self, token: str = "super-secret-token") -> None:
        self.token = token

    async def get_token(self) -> str:
        return self.token


class _FakeMqttClient:
    def __init__(self, *, fail_connect: bool = False) -> None:
        self.fail_connect = fail_connect
        self.on_connect = None
        self.on_message = None
        self.subscriptions: list[str] = []
        self.username: str | None = None
        self.password: str | None = None
        self.tls_called = False
        self.connect_calls = 0
        self.disconnect_calls = 0

    def username_pw_set(self, username: str | None = None, password: str | None = None) -> None:
        self.username = username
        self.password = password

    def tls_set(self, *args, **kwargs) -> None:
        del args, kwargs
        self.tls_called = True

    def connect(self, host: str, port: int, keepalive: int = 60) -> None:
        del host, port, keepalive
        self.connect_calls += 1
        if self.fail_connect:
            raise RuntimeError("connect failed")

    def subscribe(self, topic: str) -> tuple[int, int]:
        self.subscriptions.append(topic)
        return (0, len(self.subscriptions))

    def loop_forever(self) -> None:
        if self.on_connect is not None:
            self.on_connect(self, None, None, 0)

    def disconnect(self) -> None:
        self.disconnect_calls += 1


@pytest.mark.asyncio
async def test_mqtt_message_converts_to_raw_openf1_event() -> None:
    producer = InMemoryRawEventProducer()
    connector = OpenF1LiveMqttConnector(
        token_manager=_FakeTokenManager(),
        producer=producer,
        mqtt_client_factory=lambda: _FakeMqttClient(),
        mqtt_host="mqtt.openf1.org",
        mqtt_port=8883,
        mqtt_topics=["weather"],
        mqtt_username="openf1-user",
        reconnect_delay_seconds=0.0,
    )

    await connector.handle_message(
        "weather",
        b'{"_id":"evt-42","_key":"key-42","session_key":9149,"date":"2023-03-05T15:00:00Z","track_temperature":41.2}',
    )

    assert len(producer.events) == 1
    event = producer.events[0]
    assert event.event_id == "evt-42"
    assert event.source_id == "key-42"
    assert event.topic == RAW_OPENF1_WEATHER_TOPIC
    assert event.event_type == "openf1.weather"


@pytest.mark.asyncio
async def test_mocked_mqtt_client_uses_tls_and_subscribes_topics() -> None:
    producer = InMemoryRawEventProducer()
    fake_client = _FakeMqttClient()

    connector = OpenF1LiveMqttConnector(
        token_manager=_FakeTokenManager("super-secret-token"),
        producer=producer,
        mqtt_client_factory=lambda: fake_client,
        mqtt_host="mqtt.openf1.org",
        mqtt_port=8883,
        mqtt_topics=["weather", "location"],
        mqtt_username="openf1-user",
        reconnect_delay_seconds=0.0,
    )

    await connector.run(max_reconnect_attempts=1)

    assert fake_client.tls_called is True
    assert fake_client.username == "openf1-user"
    assert fake_client.password == "super-secret-token"
    assert fake_client.subscriptions == ["weather", "location"]


@pytest.mark.asyncio
async def test_connector_reconnect_path_retries_after_failure(caplog: pytest.LogCaptureFixture) -> None:
    first_client = _FakeMqttClient(fail_connect=True)
    second_client = _FakeMqttClient(fail_connect=False)
    clients = [first_client, second_client]

    def factory() -> _FakeMqttClient:
        return clients.pop(0)

    connector = OpenF1LiveMqttConnector(
        token_manager=_FakeTokenManager("super-secret-token"),
        producer=InMemoryRawEventProducer(),
        mqtt_client_factory=factory,
        mqtt_host="mqtt.openf1.org",
        mqtt_port=8883,
        mqtt_topics=["weather"],
        mqtt_username="openf1-user",
        reconnect_delay_seconds=0.0,
    )

    with caplog.at_level(logging.WARNING):
        await connector.run(max_reconnect_attempts=2)

    assert first_client.connect_calls == 1
    assert second_client.connect_calls == 1
    assert "reconnecting" in caplog.text.lower()


@pytest.mark.asyncio
async def test_token_manager_does_not_log_token(caplog: pytest.LogCaptureFixture) -> None:
    token_value = "super-secret-token"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/token"
        return httpx.Response(200, json={"access_token": token_value, "expires_in": 120})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.openf1.org") as http_client:
        manager = OpenF1TokenManager(
            token_url="https://api.openf1.org/token",
            username="openf1-user",
            password="openf1-password",
            http_client=http_client,
        )

        with caplog.at_level(logging.DEBUG):
            token = await manager.get_token()

    assert token == token_value
    assert token_value not in caplog.text
