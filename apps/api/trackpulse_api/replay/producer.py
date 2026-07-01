from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable

ReplaySubscriber = Callable[[dict[str, Any]], None | Awaitable[None]]
StatusSubscriber = Callable[["ReplayStatusUpdate"], None | Awaitable[None]]

SUPPORTED_SPEED_MULTIPLIERS: frozenset[int] = frozenset({1, 5, 20, 100})


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


class InMemoryEventBus:
    """Simple in-memory pub/sub bus for replay tests and local integration."""

    def __init__(self) -> None:
        self._event_subscribers: list[ReplaySubscriber] = []
        self._status_subscribers: list[StatusSubscriber] = []
        self.published_events: list[dict[str, Any]] = []
        self.status_updates: list[ReplayStatusUpdate] = []

    def subscribe_events(self, subscriber: ReplaySubscriber) -> None:
        self._event_subscribers.append(subscriber)

    def subscribe_status(self, subscriber: StatusSubscriber) -> None:
        self._status_subscribers.append(subscriber)

    async def publish_event(self, event: dict[str, Any]) -> None:
        self.published_events.append(event)
        for subscriber in self._event_subscribers:
            result = subscriber(event)
            if asyncio.iscoroutine(result):
                await result

    async def publish_status(self, status_update: ReplayStatusUpdate) -> None:
        self.status_updates.append(status_update)
        for subscriber in self._status_subscribers:
            result = subscriber(status_update)
            if asyncio.iscoroutine(result):
                await result


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
        event_bus: InMemoryEventBus,
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

                await self.event_bus.publish_event(event)
                self._published_events += 1
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
