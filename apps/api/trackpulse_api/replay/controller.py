from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from ..openf1 import OpenF1HistoricalClient, OpenF1Location, SessionDiscoveryQuery
from ..settings import AppSettings

SUPPORTED_REPLAY_SPEEDS: tuple[int, ...] = (1, 5, 10)


def _iso(value: datetime) -> str:
    return value.isoformat()


@dataclass(frozen=True)
class ReplayFixtureSummary:
    fixture_id: str
    display_name: str
    source_mode: Literal["fixture", "historical", "live"]
    supported_speeds: tuple[int, ...]


@dataclass(frozen=True)
class ReplayLocationPoint:
    occurred_at: str
    driver_number: int
    x: float
    y: float


@dataclass(frozen=True)
class ReplayCoordinateBounds:
    min_x: float
    max_x: float
    min_y: float
    max_y: float


@dataclass(frozen=True)
class ReplayStateSnapshot:
    fixture_id: str
    status: str
    speed_multiplier: int
    cursor: int
    total_points: int
    progress_pct: float
    replay_time: str | None
    active_location: ReplayLocationPoint | None
    coordinate_bounds: ReplayCoordinateBounds | None
    timeline_points: list[ReplayLocationPoint]


class FixtureReplayController:
    """In-memory fixture replay for deterministic frontend/backend integration."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._timeline: list[OpenF1Location] = []
        self._status = "idle"
        self._cursor = -1
        self._speed_multiplier = 1
        self._active_location: ReplayLocationPoint | None = None
        self._coordinate_bounds: ReplayCoordinateBounds | None = None
        self._replay_time: str | None = None
        self._stop_requested = False

    def list_fixtures(self) -> list[ReplayFixtureSummary]:
        fixture_id = self._fixture_id
        return [
            ReplayFixtureSummary(
                fixture_id=fixture_id,
                display_name=f"{self._settings.openf1_seed_country_name} {self._settings.openf1_seed_year} {self._settings.openf1_seed_session_name}",
                source_mode=self._settings.openf1_mode,
                supported_speeds=SUPPORTED_REPLAY_SPEEDS,
            )
        ]

    @property
    def _fixture_id(self) -> str:
        return "bahrain-2023-race"

    async def start(self, *, fixture_id: str, speed_multiplier: int) -> ReplayStateSnapshot:
        if speed_multiplier not in SUPPORTED_REPLAY_SPEEDS:
            raise ValueError(f"speed_multiplier must be one of {list(SUPPORTED_REPLAY_SPEEDS)}")

        if fixture_id != self._fixture_id:
            raise ValueError("fixture_id is not available")

        async with self._lock:
            if not self._timeline:
                await self._load_timeline()

            self._speed_multiplier = speed_multiplier

            if self._status == "running":
                return self.snapshot()

            if self._status == "completed" or self._cursor >= len(self._timeline) - 1:
                self._cursor = -1
                self._active_location = None
                self._replay_time = None

            self._stop_requested = False
            self._status = "running"
            self._task = asyncio.create_task(self._run())

            return self.snapshot()

    async def stop(self) -> ReplayStateSnapshot:
        async with self._lock:
            if self._status != "running":
                return self.snapshot()

            self._stop_requested = True
            self._status = "paused"
            return self.snapshot()

    def snapshot(self) -> ReplayStateSnapshot:
        total_points = len(self._timeline)
        if total_points <= 0:
            progress_pct = 0.0
        elif self._cursor < 0:
            progress_pct = 0.0
        else:
            progress_pct = round((self._cursor + 1) / total_points * 100.0, 1)

        return ReplayStateSnapshot(
            fixture_id=self._fixture_id,
            status=self._status,
            speed_multiplier=self._speed_multiplier,
            cursor=max(self._cursor, 0) if total_points > 0 else 0,
            total_points=total_points,
            progress_pct=progress_pct,
            replay_time=self._replay_time,
            active_location=self._active_location,
            coordinate_bounds=self._coordinate_bounds,
            timeline_points=[
                ReplayLocationPoint(
                    occurred_at=_iso(point.date),
                    driver_number=point.driver_number,
                    x=point.x,
                    y=point.y,
                )
                for point in self._timeline
            ],
        )

    async def shutdown(self) -> None:
        async with self._lock:
            self._stop_requested = True

        task = self._task
        if task is not None:
            await task

    async def _load_timeline(self) -> None:
        client = OpenF1HistoricalClient(
            base_url=self._settings.openf1_base_url,
            mode=self._settings.openf1_mode,
            bearer_token=self._settings.openf1_bearer_token,
            timeout_seconds=self._settings.openf1_timeout_seconds,
            max_retries=self._settings.openf1_max_retries,
            fixture_data_dir=self._settings.openf1_fixture_data_dir,
        )
        session = await client.discover_session(
            SessionDiscoveryQuery(
                year=self._settings.openf1_seed_year,
                country_name=self._settings.openf1_seed_country_name,
                session_name=self._settings.openf1_seed_session_name,
            )
        )
        timeline = await client.get_location(session_key=session.session_key)
        timeline = sorted(timeline, key=lambda record: (record.date, record.driver_number))

        self._timeline = timeline
        self._coordinate_bounds = _compute_bounds(timeline)

    async def _run(self) -> None:
        while True:
            async with self._lock:
                if self._status != "running":
                    return
                if self._stop_requested:
                    self._stop_requested = False
                    return

                next_index = self._cursor + 1
                if next_index >= len(self._timeline):
                    self._status = "completed"
                    return

                current = self._timeline[next_index]
                self._cursor = next_index
                self._replay_time = _iso(current.date)
                self._active_location = ReplayLocationPoint(
                    occurred_at=_iso(current.date),
                    driver_number=current.driver_number,
                    x=current.x,
                    y=current.y,
                )

                delay_seconds = 0.0
                if next_index + 1 < len(self._timeline):
                    current_ts = current.date.timestamp()
                    next_ts = self._timeline[next_index + 1].date.timestamp()
                    delay_seconds = max(0.0, (next_ts - current_ts) / self._speed_multiplier)

            await asyncio.sleep(delay_seconds)


def _compute_bounds(points: list[OpenF1Location]) -> ReplayCoordinateBounds | None:
    if not points:
        return None

    xs = [point.x for point in points]
    ys = [point.y for point in points]
    return ReplayCoordinateBounds(
        min_x=min(xs),
        max_x=max(xs),
        min_y=min(ys),
        max_y=max(ys),
    )