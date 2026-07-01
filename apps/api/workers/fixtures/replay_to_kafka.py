from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import logging
from pathlib import Path

from trackpulse_api.kafka import KafkaRawEventProducer, RawEventProducer, RawOpenF1Event


logger = logging.getLogger(__name__)


def _load_events(path: Path) -> list[RawOpenF1Event]:
    if not path.exists():
        raise FileNotFoundError(f"Replay events file not found: {path}")

    events: list[RawOpenF1Event] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} in {path}") from exc

            events.append(RawOpenF1Event.model_validate(parsed))

    return events


async def replay_fixture_events(
    *,
    events_path: Path,
    producer: RawEventProducer,
    limit: int | None = None,
) -> int:
    events = _load_events(events_path)
    if limit is not None:
        events = events[:limit]

    for event in events:
        await producer.publish(event)

    return len(events)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay normalized fixture events to Kafka")
    parser.add_argument("--events-path", type=Path, required=True, help="Path to normalized NDJSON events")
    parser.add_argument("--bootstrap-servers", default="localhost:9092", help="Kafka/Redpanda bootstrap servers")
    parser.add_argument("--client-id", default="trackpulse-fixture-replay", help="Kafka producer client ID")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of events to publish")
    return parser


def _build_aiokafka_client(*, bootstrap_servers: str, client_id: str):
    try:
        aiokafka = importlib.import_module("aiokafka")
    except ImportError as exc:  # pragma: no cover - dependency is optional for unit tests
        raise RuntimeError(
            "aiokafka is required for Kafka replay. Install with: pip install aiokafka"
        ) from exc

    AIOKafkaProducer = getattr(aiokafka, "AIOKafkaProducer")
    return AIOKafkaProducer(bootstrap_servers=bootstrap_servers, client_id=client_id)


async def _run(args: argparse.Namespace) -> int:
    client = _build_aiokafka_client(
        bootstrap_servers=args.bootstrap_servers,
        client_id=args.client_id,
    )

    await client.start()
    try:
        producer = KafkaRawEventProducer(client)
        published = await replay_fixture_events(
            events_path=args.events_path,
            producer=producer,
            limit=args.limit,
        )
    finally:
        await producer.close()

    logger.info("Published %d fixture events to Kafka", published)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
