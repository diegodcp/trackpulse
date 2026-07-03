"""Timeline service — orchestrates timeline build and DB caching."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from trackpulse_api.db.models.car_position import CarPosition
from trackpulse_api.db.models.car_telemetry import CarTelemetry
from trackpulse_api.db.models.car_timeline import CarTimeline
from trackpulse_api.db.models.driver import Driver
from trackpulse_api.db.models.lap import Lap
from trackpulse_api.db.models.position import Position
from trackpulse_api.db.models.session import Session
from trackpulse_api.processing.car_timeline_builder import (
    CarFrame,
    TimelineFrame,
    build_car_timeline,
)
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError

logger = logging.getLogger(__name__)


class TimelineService:
    """Orchestrates car timeline generation: fetch data → build → store/retrieve."""

    def __init__(self, db_session: AsyncSession):
        self._db = db_session

    async def get_timeline_meta(
        self, session_key: int, target_hz: float = 2.0, chunk_seconds: float = 120.0
    ) -> dict:
        """Return lightweight timeline metadata without loading position arrays.

        Queries only drivers + timeline time range. Response < 2KB.
        """
        # Find session
        result = await self._db.execute(
            select(Session).where(Session.session_key == session_key)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise SessionNotFoundError(f"Session with key {session_key} not found")

        # Get time range from CarTimeline (min/max timestamp)
        range_result = await self._db.execute(
            select(
                func.min(CarTimeline.timestamp).label("first_ts"),
                func.max(CarTimeline.timestamp).label("last_ts"),
            ).where(CarTimeline.session_id == session.id)
        )
        row = range_result.one()
        if row.first_ts is None or row.last_ts is None:
            raise InsufficientDataError("No car timeline data found for this session")

        total_duration = (row.last_ts - row.first_ts).total_seconds()

        # Get drivers
        driver_result = await self._db.execute(
            select(Driver).where(Driver.session_id == session.id)
        )
        drivers = [
            {
                "driver_number": d.driver_number,
                "name_acronym": d.name_acronym,
                "team_colour": d.team_colour,
            }
            for d in driver_result.scalars().all()
        ]

        total_chunks = max(1, int(total_duration / chunk_seconds) + (
            1 if total_duration % chunk_seconds > 0 else 0
        ))

        return {
            "session_key": session_key,
            "total_duration_seconds": round(total_duration, 3),
            "target_hz": target_hz,
            "total_chunks": total_chunks,
            "chunk_seconds": chunk_seconds,
            "drivers": drivers,
        }

    async def get_driver_speed_series(
        self, session_key: int, driver_number: int
    ) -> tuple[list[float], list[float]]:
        """Return raw elapsed-seconds and speed arrays for a single driver.

        Reads from the pre-computed CarTimeline table. Returns two parallel
        lists: (elapsed_seconds[], speed[]) with NaN gaps excluded.
        """
        # Find session
        result = await self._db.execute(
            select(Session).where(Session.session_key == session_key)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise SessionNotFoundError(f"Session with key {session_key} not found")

        # Query timeline rows for this driver, ordered by timestamp
        rows_result = await self._db.execute(
            select(CarTimeline.timestamp, CarTimeline.speed)
            .where(
                CarTimeline.session_id == session.id,
                CarTimeline.driver_number == driver_number,
            )
            .order_by(CarTimeline.timestamp)
        )
        rows = rows_result.all()
        if not rows:
            raise InsufficientDataError(
                f"No timeline data for driver {driver_number} in session {session_key}"
            )

        # Compute elapsed seconds from first timestamp and filter out null speeds
        first_ts = rows[0].timestamp
        elapsed = []
        speeds = []
        for row in rows:
            if row.speed is not None:
                elapsed.append((row.timestamp - first_ts).total_seconds())
                speeds.append(float(row.speed))

        if not elapsed:
            raise InsufficientDataError(
                f"No speed data for driver {driver_number} in session {session_key}"
            )

        return elapsed, speeds

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

    async def get_compact_chunk(
        self,
        session_key: int,
        chunk_index: int,
        chunk_seconds: float = 30.0,
        target_hz: float = 2.0,
    ) -> dict | None:
        """Load a single chunk directly from DB without loading the full timeline.

        Queries only the CarTimeline rows within the requested time window.
        Returns dict with all data needed for CompactChunkResponse, or None
        if no pre-computed timeline exists (caller should fall back to build).
        """
        # 1. Find session
        result = await self._db.execute(
            select(Session).where(Session.session_key == session_key)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise SessionNotFoundError(f"Session with key {session_key} not found")

        # 2. Get time range (fast — uses index)
        range_result = await self._db.execute(
            select(
                func.min(CarTimeline.timestamp).label("first_ts"),
                func.max(CarTimeline.timestamp).label("last_ts"),
            ).where(CarTimeline.session_id == session.id)
        )
        row = range_result.one()
        if row.first_ts is None or row.last_ts is None:
            return None  # No cached data — caller should build

        first_ts = row.first_ts
        total_duration = (row.last_ts - first_ts).total_seconds()
        total_chunks = max(1, int(total_duration / chunk_seconds) + (
            1 if total_duration % chunk_seconds > 0 else 0
        ))

        if chunk_index >= total_chunks:
            return None  # Chunk out of range

        # 3. Compute chunk time window
        chunk_start_sec = chunk_index * chunk_seconds
        chunk_end_sec = min((chunk_index + 1) * chunk_seconds, total_duration)
        ts_start = first_ts + timedelta(seconds=chunk_start_sec)
        ts_end = first_ts + timedelta(seconds=chunk_end_sec)

        # 4. Query ONLY the rows in this chunk's time window (uses idx_car_timeline_session_ts)
        chunk_result = await self._db.execute(
            select(
                CarTimeline.timestamp,
                CarTimeline.driver_number,
                CarTimeline.x,
                CarTimeline.y,
                CarTimeline.speed,
                CarTimeline.position,
                CarTimeline.lap_number,
            )
            .where(
                CarTimeline.session_id == session.id,
                CarTimeline.timestamp >= ts_start,
                CarTimeline.timestamp <= ts_end,
            )
            .order_by(CarTimeline.timestamp, CarTimeline.driver_number)
        )
        rows = chunk_result.all()

        if not rows:
            # Empty chunk — return valid but empty response
            drivers = await self._get_drivers(session.id)
            return {
                "session_key": session_key,
                "total_duration_seconds": round(total_duration, 3),
                "target_hz": target_hz,
                "total_chunks": total_chunks,
                "chunk_index": chunk_index,
                "chunk_start_seconds": round(chunk_start_sec, 3),
                "chunk_end_seconds": round(chunk_end_sec, 3),
                "frame_count": 0,
                "drivers": drivers,
                "elapsed": [],
                "positions": {},
            }

        # 5. Get driver metadata
        drivers = await self._get_drivers(session.id)
        driver_map = {d["driver_number"]: d for d in drivers}

        # 6. Build columnar response directly from rows (no intermediate objects)
        elapsed_list: list[float] = []
        driver_numbers_seen: set[int] = set()
        positions: dict[str, dict[str, list]] = {}

        current_ts = None
        for r in rows:
            driver_numbers_seen.add(r.driver_number)

        # Initialize position arrays
        driver_numbers = sorted(driver_numbers_seen)
        for dn in driver_numbers:
            positions[str(dn)] = {"x": [], "y": [], "speed": [], "position": [], "lap": []}

        # Group by timestamp and build columnar data
        current_ts = None
        frame_drivers: dict[int, object] = {}

        for r in rows:
            if r.timestamp != current_ts:
                # Flush previous frame
                if current_ts is not None:
                    elapsed = (current_ts - first_ts).total_seconds()
                    elapsed_list.append(round(elapsed, 3))
                    for dn in driver_numbers:
                        d = frame_drivers.get(dn)
                        if d:
                            positions[str(dn)]["x"].append(round(d.x, 1))
                            positions[str(dn)]["y"].append(round(d.y, 1))
                            positions[str(dn)]["speed"].append(d.speed)
                            positions[str(dn)]["position"].append(d.position)
                            positions[str(dn)]["lap"].append(d.lap_number)
                        else:
                            positions[str(dn)]["x"].append(None)
                            positions[str(dn)]["y"].append(None)
                            positions[str(dn)]["speed"].append(None)
                            positions[str(dn)]["position"].append(None)
                            positions[str(dn)]["lap"].append(None)

                current_ts = r.timestamp
                frame_drivers = {}

            frame_drivers[r.driver_number] = r

        # Flush last frame
        if current_ts is not None:
            elapsed = (current_ts - first_ts).total_seconds()
            elapsed_list.append(round(elapsed, 3))
            for dn in driver_numbers:
                d = frame_drivers.get(dn)
                if d:
                    positions[str(dn)]["x"].append(round(d.x, 1))
                    positions[str(dn)]["y"].append(round(d.y, 1))
                    positions[str(dn)]["speed"].append(d.speed)
                    positions[str(dn)]["position"].append(d.position)
                    positions[str(dn)]["lap"].append(d.lap_number)
                else:
                    positions[str(dn)]["x"].append(None)
                    positions[str(dn)]["y"].append(None)
                    positions[str(dn)]["speed"].append(None)
                    positions[str(dn)]["position"].append(None)
                    positions[str(dn)]["lap"].append(None)

        # Use all session drivers (not just seen in this chunk) for driver list
        return {
            "session_key": session_key,
            "total_duration_seconds": round(total_duration, 3),
            "target_hz": target_hz,
            "total_chunks": total_chunks,
            "chunk_index": chunk_index,
            "chunk_start_seconds": round(chunk_start_sec, 3),
            "chunk_end_seconds": round(chunk_end_sec, 3),
            "frame_count": len(elapsed_list),
            "drivers": drivers,
            "elapsed": elapsed_list,
            "positions": positions,
        }

    async def _get_drivers(self, session_id: int) -> list[dict]:
        """Load driver metadata for a session."""
        driver_result = await self._db.execute(
            select(Driver).where(Driver.session_id == session_id)
        )
        return [
            {
                "driver_number": d.driver_number,
                "name_acronym": d.name_acronym,
                "team_colour": d.team_colour,
            }
            for d in driver_result.scalars().all()
        ]

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
