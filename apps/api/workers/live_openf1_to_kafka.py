from __future__ import annotations

import argparse
import asyncio
import importlib
import logging

from trackpulse_api.kafka import KafkaRawEventProducer
from trackpulse_api.openf1 import OpenF1LiveMqttConnector, OpenF1TokenManager
from trackpulse_api.settings import AppSettings


logger = logging.getLogger(__name__)


def _parse_topics(raw_topics: str) -> list[str]:
    return [topic.strip() for topic in raw_topics.split(",") if topic.strip()]


def _build_mqtt_client():
    try:
        mqtt = importlib.import_module("paho.mqtt.client")
    except ImportError as exc:  # pragma: no cover - optional dependency for unit tests
        raise RuntimeError("paho-mqtt is required for live MQTT ingestion. Install with: pip install paho-mqtt") from exc

    Client = getattr(mqtt, "Client")
    return Client()


def _build_aiokafka_client(*, bootstrap_servers: str, client_id: str):
    try:
        aiokafka = importlib.import_module("aiokafka")
    except ImportError as exc:  # pragma: no cover - optional dependency for unit tests
        raise RuntimeError(
            "aiokafka is required for Kafka ingestion. Install with: pip install aiokafka"
        ) from exc

    AIOKafkaProducer = getattr(aiokafka, "AIOKafkaProducer")
    return AIOKafkaProducer(bootstrap_servers=bootstrap_servers, client_id=client_id)


def _validate_live_settings(settings: AppSettings) -> None:
    if settings.openf1_mode != "live":
        raise RuntimeError("TRACKPULSE_OPENF1_MODE must be 'live' for live MQTT ingestion")
    if not settings.openf1_username or not settings.openf1_password:
        raise RuntimeError("TRACKPULSE_OPENF1_USERNAME and TRACKPULSE_OPENF1_PASSWORD are required in live mode")


async def _run(args: argparse.Namespace) -> int:
    settings = AppSettings()
    _validate_live_settings(settings)

    token_manager = OpenF1TokenManager(
        token_url=settings.openf1_token_url,
        username=settings.openf1_username,
        password=settings.openf1_password,
        timeout_seconds=settings.openf1_timeout_seconds,
    )

    kafka_client = _build_aiokafka_client(
        bootstrap_servers=args.bootstrap_servers,
        client_id=args.client_id,
    )
    await kafka_client.start()

    producer = KafkaRawEventProducer(kafka_client)
    connector = OpenF1LiveMqttConnector(
        token_manager=token_manager,
        producer=producer,
        mqtt_client_factory=_build_mqtt_client,
        mqtt_host=settings.openf1_live_mqtt_host,
        mqtt_port=settings.openf1_live_mqtt_port,
        mqtt_topics=_parse_topics(settings.openf1_live_mqtt_topics),
        mqtt_username=settings.openf1_username,
        reconnect_delay_seconds=settings.openf1_live_reconnect_delay_seconds,
    )

    try:
        await connector.run()
    finally:
        await producer.close()

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest OpenF1 live MQTT messages into Kafka")
    parser.add_argument("--bootstrap-servers", default="localhost:9092", help="Kafka/Redpanda bootstrap servers")
    parser.add_argument("--client-id", default="trackpulse-openf1-live", help="Kafka producer client ID")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
