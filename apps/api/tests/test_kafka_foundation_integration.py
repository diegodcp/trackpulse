from __future__ import annotations

import os
from pathlib import Path

import pytest

from workers.fixtures import replay_to_kafka


@pytest.mark.integration
def test_replay_cli_requires_aiokafka_and_can_be_smoke_invoked(tmp_path: Path) -> None:
    bootstrap_servers = os.getenv("TRACKPULSE_KAFKA_BOOTSTRAP_SERVERS")
    if not bootstrap_servers:
        pytest.skip("Set TRACKPULSE_KAFKA_BOOTSTRAP_SERVERS to run Kafka integration test")

    events_path = tmp_path / "events.ndjson"
    events_path.write_text(
        '{"event_id":"evt-001","fixture_id":"bahrain-2023-race","source":"openf1-fixture","topic":"raw.openf1.weather.v1","event_type":"openf1.weather","occurred_at":"2023-03-05T15:00:00Z","payload":{"track_temperature":42.0}}\n',
        encoding="utf-8",
    )

    # This test is opt-in and broker-backed by design.
    exit_code = replay_to_kafka.main(
        [
            "--events-path",
            str(events_path),
            "--bootstrap-servers",
            bootstrap_servers,
            "--limit",
            "1",
        ]
    )

    assert exit_code == 0
