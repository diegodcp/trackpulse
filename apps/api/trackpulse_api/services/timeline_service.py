"""Timeline service — orchestrates timeline build and DB caching."""

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trackpulse_api.db.models.car_position import CarPosition
from trackpulse_api.db.models.car_telemetry import CarTelemetry
from trackpulse_api.db.models.car_timeline import CarTimeline
from trackpulse_api.db.models.driver import Driver
from trackpulse_api.db.models.lap import Lap
from trackpulse_api.db.models.position import Position
from trackpulse_api.db.models.session import Session
from trackpulse_api.processing.car_timeline_builder import (
    TimelineFrame,
    build_car_timeline,
)
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError

logger = logging.getLogger(__name__)


class TimelineService:
    """Orchestrates car timeline generation: fetch data → build → store/retrieve."""

    def __init__(self, db_session: AsyncSession):
        self._db = db_session

    async def get_or_build_car_timeline(
        self, session_key: int, target_hz: float = 4.0
    ) -> list[TimelineFrame]:
        """Return cached car timeline or build from ingested data."""
        # 1. Find session
        result = await self._db.execute(
            select(Session).where(Session.session_key == session_key)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise SessionNotFoundError(f"Session with key {session_key} not found")

        # 2. Check cache
        cached = await self._load_from_db(session.id, target_hz)
        if cached:
            return cached

        # 3. Build from raw data
        timeline = await self._build_timeline(session.id, target_hz)

        # 4. Store in DB
        await self._store_timeline(session.id, timeline)

        return timeline

    async def _load_from_db(
        self, session_id: int, target_hz: float
    ) -> list[TimelineFrame] | None:
        """Load pre-computed timeline from car_timeline table."""
        # Check if any data exists for this session
        count_result = await self._db.execute(
            select(func.count(CarTimeline.id)).where(
                CarTimeline.session_id == session_id
            )
        )
        count = count_result.scalar()
        if not count:
            return None

        # Load all timeline rows ordered by timestamp
        result = await self._db.execute(
            select(CarTimeline)
            .where(CarTimeline.session_id == session_id)
            .order_by(CarTimeline.timestamp)
        )
        rows = result.scalars().all()
        if not rows:
            return None

        # Load drivers for metadata
        driver_result = await self._db.execute(
            select(Driver).where(Driver.session_id == session_id)
        )
        driver_rows = driver_result.scalars().all()
        driver_map = {
            d.driver_number: {"name_acronym": d.name_acronym, "team_colour": d.team_colour}
            for d in driver_rows
        }

        # Group rows by timestamp → frames
        from trackpulse_api.processing.car_timeline_builder import CarFrame

        frames: list[TimelineFrame] = []
        current_ts = None
        current_cars: list[CarFrame] = []
        first_ts = rows[0].timestamp

        for row in rows:
            if row.timestamp != current_ts:
                if current_ts is not None:
                    elapsed = (current_ts - first_ts).total_seconds()
                    frames.append(TimelineFrame(
                        timestamp=current_ts.isoformat(),
                        elapsed_seconds=round(elapsed, 3),
                        cars=current_cars,
                    ))
                current_ts = row.timestamp
                current_cars = []

            meta = driver_map.get(row.driver_number, {})
            current_cars.append(CarFrame(
                driver_number=row.driver_number,
                x=round(row.x, 1),
                y=round(row.y, 1),
                speed=row.speed,
                position=row.position,
                lap_number=row.lap_number,
                name_acronym=meta.get("name_acronym", ""),
                team_colour=meta.get("team_colour", "FFFFFF"),
            ))

        # Don't forget last group
        if current_ts is not None and current_cars:
            elapsed = (current_ts - first_ts).total_seconds()
            frames.append(TimelineFrame(
                timestamp=current_ts.isoformat(),
                elapsed_seconds=round(elapsed, 3),
                cars=current_cars,
            ))

        return frames

    async def _build_timeline(
        self, session_id: int, target_hz: float
    ) -> list[TimelineFrame]:
        """Build timeline from raw ingested data."""
        # Fetch raw positions
        pos_result = await self._db.execute(
            select(CarPosition)
            .where(CarPosition.session_id == session_id)
            .order_by(CarPosition.timestamp)
        )
        raw_positions_rows = pos_result.scalars().all()
        if not raw_positions_rows:
            raise InsufficientDataError("No car position data found for this session")

        raw_positions = [
            {
                "driver_number": r.driver_number,
                "timestamp": r.timestamp,
                "x": r.x,
                "y": r.y,
            }
            for r in raw_positions_rows
        ]

        # Fetch telemetry (speed)
        tel_result = await self._db.execute(
            select(CarTelemetry)
            .where(CarTelemetry.session_id == session_id)
            .order_by(CarTelemetry.timestamp)
        )
        raw_telemetry = [
            {
                "driver_number": r.driver_number,
                "timestamp": r.timestamp,
                "speed": r.speed,
            }
            for r in tel_result.scalars().all()
        ]

        # Fetch race positions
        rp_result = await self._db.execute(
            select(Position)
            .where(Position.session_id == session_id)
            .order_by(Position.timestamp)
        )
        raw_positions_data = [
            {
                "driver_number": r.driver_number,
                "timestamp": r.timestamp,
                "position": r.position,
            }
            for r in rp_result.scalars().all()
        ]

        # Fetch laps
        laps_result = await self._db.execute(
            select(Lap)
            .where(Lap.session_id == session_id)
            .order_by(Lap.date_start)
        )
        raw_laps = [
            {
                "driver_number": r.driver_number,
                "lap_number": r.lap_number,
                "date_start": r.date_start,
                "timestamp": r.date_start,  # for forward-fill
            }
            for r in laps_result.scalars().all()
            if r.date_start is not None
        ]

        # Fetch drivers
        driver_result = await self._db.execute(
            select(Driver).where(Driver.session_id == session_id)
        )
        drivers = [
            {
                "driver_number": d.driver_number,
                "name_acronym": d.name_acronym,
                "team_colour": d.team_colour,
            }
            for d in driver_result.scalars().all()
        ]

        if not drivers:
            raise InsufficientDataError("No driver data found for this session")

        # Build (pure function)
        timeline = build_car_timeline(
            raw_positions=raw_positions,
            raw_telemetry=raw_telemetry,
            raw_positions_data=raw_positions_data,
            raw_laps=raw_laps,
            drivers=drivers,
            target_hz=target_hz,
        )

        logger.info(
            "Built car timeline for session_id=%d: %d frames at %.1f Hz",
            session_id,
            len(timeline),
            target_hz,
        )
        return timeline

    async def _store_timeline(
        self, session_id: int, timeline: list[TimelineFrame]
    ) -> None:
        """Persist computed timeline to car_timeline table."""
        # Clear any existing data for this session
        await self._db.execute(
            delete(CarTimeline).where(CarTimeline.session_id == session_id)
        )

        # Batch insert
        from datetime import datetime as dt

        rows = []
        for frame in timeline:
            ts = datetime.fromisoformat(frame.timestamp)
            for car in frame.cars:
                rows.append(CarTimeline(
                    session_id=session_id,
                    timestamp=ts,
                    driver_number=car.driver_number,
                    x=car.x,
                    y=car.y,
                    speed=car.speed,
                    position=car.position,
                    lap_number=car.lap_number,
                ))

        # Insert in batches of 10000 to avoid memory issues
        batch_size = 10000
        for i in range(0, len(rows), batch_size):
            self._db.add_all(rows[i : i + batch_size])
            await self._db.flush()

        await self._db.commit()
        logger.info(
            "Stored %d car_timeline rows for session_id=%d", len(rows), session_id
        )
