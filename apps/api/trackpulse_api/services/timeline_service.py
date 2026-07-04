"""Timeline service — orchestrates timeline build and DB caching."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from trackpulse_api.db.models.car_position import CarPosition
from trackpulse_api.db.models.car_telemetry import CarTelemetry
from trackpulse_api.db.models.car_timeline import CarTimeline
from trackpulse_api.db.models.circuit_geometry import CircuitGeometry as CircuitGeometryModel
from trackpulse_api.db.models.driver import Driver
from trackpulse_api.db.models.lap import Lap
from trackpulse_api.db.models.position import Position
from trackpulse_api.db.models.race_control_event import RaceControlEvent
from trackpulse_api.db.models.session import Session
from trackpulse_api.db.models.weather_sample import WeatherSample
from trackpulse_api.processing.car_timeline_builder import (
    CarFrame,
    TimelineFrame,
    build_car_timeline,
)
from trackpulse_api.processing.weather_timeline_builder import (
    WeatherState,
    align_weather_to_timeline,
)
from trackpulse_api.processing.wind_derivation import (
    SegmentWind,
    derive_segment_wind,
)
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError

logger = logging.getLogger(__name__)

# Formation lap typically takes 3-4 minutes; we use a conservative buffer
# so the timeline starts a bit before cars leave the grid.
_FORMATION_LAP_OFFSET_SECONDS = 240


class TimelineService:
    """Orchestrates car timeline generation: fetch data → build → store/retrieve."""

    def __init__(self, db_session: AsyncSession):
        self._db = db_session

    async def _get_race_start_timestamp(self, session_id: int) -> datetime | None:
        """Find the 'SESSION STARTED' timestamp from race_control_events.

        Returns None if no such event exists (e.g. practice/qualifying sessions).
        """
        result = await self._db.execute(
            select(RaceControlEvent.timestamp)
            .where(
                RaceControlEvent.session_id == session_id,
                RaceControlEvent.category == "SessionStatus",
                RaceControlEvent.message.ilike("%STARTED%"),
            )
            .order_by(RaceControlEvent.timestamp)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row

    async def _get_effective_start(self, session: Session) -> datetime | None:
        """Determine the effective timeline start for race sessions.

        For Race/Sprint sessions, returns formation lap start time
        (SESSION STARTED minus offset). For other session types returns None
        (use all data from first position).
        """
        if session.session_type not in ("Race", "Sprint"):
            return None

        race_start_ts = await self._get_race_start_timestamp(session.id)
        if race_start_ts is None:
            return None

        formation_start = race_start_ts - timedelta(seconds=_FORMATION_LAP_OFFSET_SECONDS)
        return formation_start

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

        # Compute race start offset relative to the (trimmed) timeline start
        race_start_elapsed: float | None = None
        race_start_ts = await self._get_race_start_timestamp(session.id)
        if race_start_ts is not None and row.first_ts is not None:
            offset = (race_start_ts - row.first_ts).total_seconds()
            if 0 <= offset <= total_duration:
                race_start_elapsed = round(offset, 3)

        return {
            "session_key": session_key,
            "total_duration_seconds": round(total_duration, 3),
            "target_hz": target_hz,
            "total_chunks": total_chunks,
            "chunk_seconds": chunk_seconds,
            "drivers": drivers,
            "race_start_elapsed_seconds": race_start_elapsed,
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

        # 3. Build from raw data (with race-phase filtering for Race/Sprint)
        timeline = await self._build_timeline(session.id, target_hz, session=session)

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

        # Compute race start offset (only needed for chunk 0 but cheap to compute)
        race_start_elapsed: float | None = None
        race_start_ts = await self._get_race_start_timestamp(session.id)
        if race_start_ts is not None:
            offset = (race_start_ts - first_ts).total_seconds()
            if 0 <= offset <= total_duration:
                race_start_elapsed = round(offset, 3)

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

        # Align weather to this chunk's timestamps
        weather_states = await self.get_weather_for_chunk(
            session.id, first_ts, elapsed_list
        )

        # Derive per-segment wind from weather + circuit geometry
        segment_wind_frames = None
        if weather_states:
            segment_wind_frames = await self.get_segment_wind_for_chunk(
                session.id, weather_states
            )

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
            "weather": weather_states,
            "segment_wind": segment_wind_frames,
            "race_start_elapsed_seconds": race_start_elapsed,
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
        self, session_id: int, target_hz: float, session: Session | None = None
    ) -> list[TimelineFrame]:
        """Build timeline from raw ingested data.

        For Race/Sprint sessions, trims pre-race data by starting the timeline
        from the formation lap (SESSION STARTED minus offset). This avoids
        loading ~1h of reconnaissance/grid data that has no animation value.
        """
        # Determine effective start (formation lap for races, None for others)
        effective_start: datetime | None = None
        if session is not None:
            effective_start = await self._get_effective_start(session)

        # Fetch raw positions — filtered by effective_start if set
        pos_query = (
            select(CarPosition)
            .where(CarPosition.session_id == session_id)
            .order_by(CarPosition.timestamp)
        )
        if effective_start is not None:
            pos_query = pos_query.where(CarPosition.timestamp >= effective_start)

        pos_result = await self._db.execute(pos_query)
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

        # Fetch telemetry (speed) — filtered
        tel_query = (
            select(CarTelemetry)
            .where(CarTelemetry.session_id == session_id)
            .order_by(CarTelemetry.timestamp)
        )
        if effective_start is not None:
            tel_query = tel_query.where(CarTelemetry.timestamp >= effective_start)

        tel_result = await self._db.execute(tel_query)
        raw_telemetry = [
            {
                "driver_number": r.driver_number,
                "timestamp": r.timestamp,
                "speed": r.speed,
            }
            for r in tel_result.scalars().all()
        ]

        # Fetch race positions — filtered
        rp_query = (
            select(Position)
            .where(Position.session_id == session_id)
            .order_by(Position.timestamp)
        )
        if effective_start is not None:
            rp_query = rp_query.where(Position.timestamp >= effective_start)

        rp_result = await self._db.execute(rp_query)
        raw_positions_data = [
            {
                "driver_number": r.driver_number,
                "timestamp": r.timestamp,
                "position": r.position,
            }
            for r in rp_result.scalars().all()
        ]

        # Fetch laps (all — needed for forward-fill context)
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

    async def get_weather_for_chunk(
        self,
        session_id: int,
        first_ts: datetime,
        elapsed_list: list[float],
    ) -> list[WeatherState] | None:
        """Fetch weather samples and align to a chunk's elapsed grid.

        Returns None if no weather data is available for the session.
        """
        result = await self._db.execute(
            select(WeatherSample)
            .where(WeatherSample.session_id == session_id)
            .order_by(WeatherSample.timestamp)
        )
        rows = result.scalars().all()
        if not rows:
            return None

        weather_samples = [
            {
                "timestamp": r.timestamp,
                "air_temperature": r.air_temperature or 0.0,
                "track_temperature": r.track_temperature or 0.0,
                "humidity": r.humidity or 0.0,
                "wind_speed": r.wind_speed or 0.0,
                "wind_direction": r.wind_direction or 0,
                "rainfall": r.rainfall or False,
            }
            for r in rows
        ]

        # Convert elapsed seconds to absolute timestamps for alignment
        grid_timestamps = [
            first_ts + timedelta(seconds=e) for e in elapsed_list
        ]

        return align_weather_to_timeline(weather_samples, grid_timestamps)

    async def get_session_id(self, session_key: int) -> int:
        """Resolve a public session_key to an internal session id."""
        result = await self._db.execute(
            select(Session.id).where(Session.session_key == session_key)
        )
        session_id = result.scalar_one_or_none()
        if session_id is None:
            raise SessionNotFoundError(f"Session with key {session_key} not found")
        return session_id

    async def get_segment_wind_for_chunk(
        self,
        session_id: int,
        weather_states: list[WeatherState],
    ) -> list[list[SegmentWind]] | None:
        """Derive per-segment wind for each frame from weather + circuit geometry.

        Returns None if no circuit geometry is available for the session.
        Each inner list has one SegmentWind per circuit segment.
        """
        # Fetch circuit geometry from DB
        result = await self._db.execute(
            select(CircuitGeometryModel).where(
                CircuitGeometryModel.session_id == session_id
            )
        )
        geo_row = result.scalar_one_or_none()
        if not geo_row:
            return None

        circuit_points = geo_row.centerline  # list of {x, y, cumulative_dist}
        segments = geo_row.segments  # list of {id, start_idx, end_idx, ...}

        # Derive wind for each weather frame (pure function, no I/O)
        segment_wind_frames: list[list[SegmentWind]] = []
        for weather in weather_states:
            frame_wind = derive_segment_wind(
                wind_speed=weather.wind_speed,
                wind_direction=weather.wind_direction,
                circuit_points=circuit_points,
                segments=segments,
            )
            segment_wind_frames.append(frame_wind)

        return segment_wind_frames
