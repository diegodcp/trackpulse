import logging
from datetime import datetime
from enum import Enum

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from trackpulse_api.clients.openf1 import OpenF1ClientProtocol
from trackpulse_api.db.models.car_position import CarPosition
from trackpulse_api.db.models.car_telemetry import CarTelemetry
from trackpulse_api.db.models.driver import Driver
from trackpulse_api.db.models.interval import Interval
from trackpulse_api.db.models.lap import Lap
from trackpulse_api.db.models.pit_stop import PitStop
from trackpulse_api.db.models.position import Position
from trackpulse_api.db.models.race_control_event import RaceControlEvent
from trackpulse_api.db.models.session import Session
from trackpulse_api.db.models.stint import Stint
from trackpulse_api.db.models.weather_sample import WeatherSample

logger = logging.getLogger(__name__)


def _parse_dt(value) -> datetime | None:
    """Parse an ISO datetime string into a Python datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


class IngestStage(str, Enum):
    DRIVERS = "drivers"
    WEATHER = "weather"
    LOCATION = "location"
    CAR_DATA = "car_data"
    LAPS = "laps"
    STINTS = "stints"
    RACE_CONTROL = "race_control"
    INTERVALS = "intervals"
    POSITIONS = "positions"
    PIT_STOPS = "pit_stops"


ALL_STAGES = [stage.value for stage in IngestStage]


class IngestService:
    """Orchestrates downloading all OpenF1 data for a session."""

    def __init__(self, openf1_client: OpenF1ClientProtocol, db_session: AsyncSession):
        self._client = openf1_client
        self._db = db_session

    async def start_ingest(self, session_key: int) -> None:
        """
        Download all data types for a session.

        Downloads in dependency order:
        1. drivers (needed for other queries)
        2. weather, laps, stints, race_control, pit_stops (independent, medium)
        3. location, car_data, intervals, positions (large, parallelized)

        Idempotent: skips stages already completed for this session.
        """
        session_id = await self._get_session_id(session_key)

        await self._update_session_status(session_key, "in_progress")

        try:
            # Stage 1: Drivers (must come first)
            await self._ingest_drivers(session_key, session_id)

            # Stage 2: Small/medium data (sequential to avoid session conflicts)
            await self._ingest_weather(session_key, session_id)
            await self._ingest_laps(session_key, session_id)
            await self._ingest_stints(session_key, session_id)
            await self._ingest_race_control(session_key, session_id)
            await self._ingest_pit_stops(session_key, session_id)

            # Stage 3: Large data (sequential for DB session safety)
            await self._ingest_location(session_key, session_id)
            await self._ingest_car_data(session_key, session_id)
            await self._ingest_intervals(session_key, session_id)
            await self._ingest_positions(session_key, session_id)

            await self._update_session_status(session_key, "complete")
        except Exception:
            await self._update_session_status(session_key, "failed")
            raise

    async def get_progress(self, session_key: int) -> dict:
        """Get current ingest progress for a session."""
        session_id = await self._get_session_id(session_key)

        # Get session status
        result = await self._db.execute(
            select(Session.ingest_status).where(Session.session_key == session_key)
        )
        status = result.scalar_one_or_none() or "pending"

        # Count rows per stage
        rows_ingested: dict[str, int] = {}
        stages_complete: list[str] = []
        stages_remaining: list[str] = []

        stage_checks = [
            (IngestStage.DRIVERS, Driver, "session_id"),
            (IngestStage.WEATHER, WeatherSample, "session_id"),
            (IngestStage.LOCATION, CarPosition, "session_id"),
            (IngestStage.CAR_DATA, CarTelemetry, "session_id"),
            (IngestStage.LAPS, Lap, "session_id"),
            (IngestStage.STINTS, Stint, "session_id"),
            (IngestStage.RACE_CONTROL, RaceControlEvent, "session_id"),
            (IngestStage.INTERVALS, Interval, "session_id"),
            (IngestStage.POSITIONS, Position, "session_id"),
            (IngestStage.PIT_STOPS, PitStop, "session_id"),
        ]

        for stage, model, fk_col in stage_checks:
            count = await self._count_rows(model, session_id)
            rows_ingested[stage.value] = count
            if count > 0:
                stages_complete.append(stage.value)
            else:
                stages_remaining.append(stage.value)

        return {
            "session_key": session_key,
            "status": status,
            "stages_complete": stages_complete,
            "stages_remaining": stages_remaining,
            "rows_ingested": rows_ingested,
        }

    # --- Private ingest methods ---

    async def _ingest_drivers(self, session_key: int, session_id: int) -> None:
        count = await self._count_rows(Driver, session_id)
        if count > 0:
            return

        raw = await self._client.get_drivers(session_key)
        records = [
            {
                "session_id": session_id,
                "driver_number": r.get("driver_number"),
                "full_name": r.get("full_name", ""),
                "name_acronym": r.get("name_acronym", ""),
                "team_name": r.get("team_name", ""),
                "team_colour": r.get("team_colour", "000000"),
                "headshot_url": r.get("headshot_url"),
            }
            for r in raw
        ]
        await self._bulk_insert(Driver, records)
        logger.info("Ingested %d drivers for session %d", len(records), session_key)

    async def _ingest_weather(self, session_key: int, session_id: int) -> None:
        count = await self._count_rows(WeatherSample, session_id)
        if count > 0:
            return

        raw = await self._client.get_weather(session_key)
        records = [
            {
                "session_id": session_id,
                "timestamp": _parse_dt(r.get("date")),
                "air_temperature": r.get("air_temperature"),
                "track_temperature": r.get("track_temperature"),
                "humidity": r.get("humidity"),
                "pressure": r.get("pressure"),
                "wind_speed": r.get("wind_speed"),
                "wind_direction": r.get("wind_direction"),
                "rainfall": r.get("rainfall"),
            }
            for r in raw
        ]
        await self._bulk_insert(WeatherSample, records)
        logger.info("Ingested %d weather samples for session %d", len(records), session_key)

    async def _ingest_location(self, session_key: int, session_id: int) -> None:
        count = await self._count_rows(CarPosition, session_id)
        if count > 0:
            return

        raw = await self._client.get_location(session_key)
        records = [
            {
                "session_id": session_id,
                "driver_number": r.get("driver_number"),
                "timestamp": _parse_dt(r.get("date")),
                "x": r.get("x"),
                "y": r.get("y"),
                "z": r.get("z"),
            }
            for r in raw
        ]
        await self._bulk_insert(CarPosition, records)
        logger.info("Ingested %d car positions for session %d", len(records), session_key)

    async def _ingest_car_data(self, session_key: int, session_id: int) -> None:
        count = await self._count_rows(CarTelemetry, session_id)
        if count > 0:
            return

        raw = await self._client.get_car_data(session_key)
        records = [
            {
                "session_id": session_id,
                "driver_number": r.get("driver_number"),
                "timestamp": _parse_dt(r.get("date")),
                "speed": r.get("speed", 0),
                "throttle": r.get("throttle"),
                "brake": r.get("brake"),
                "n_gear": r.get("n_gear"),
                "rpm": r.get("rpm"),
                "drs": r.get("drs"),
            }
            for r in raw
        ]
        await self._bulk_insert(CarTelemetry, records)
        logger.info("Ingested %d car telemetry for session %d", len(records), session_key)

    async def _ingest_laps(self, session_key: int, session_id: int) -> None:
        count = await self._count_rows(Lap, session_id)
        if count > 0:
            return

        raw = await self._client.get_laps(session_key)
        records = [
            {
                "session_id": session_id,
                "driver_number": r.get("driver_number"),
                "lap_number": r.get("lap_number"),
                "lap_duration": r.get("lap_duration"),
                "duration_sector_1": r.get("duration_sector_1"),
                "duration_sector_2": r.get("duration_sector_2"),
                "duration_sector_3": r.get("duration_sector_3"),
                "i1_speed": r.get("i1_speed"),
                "i2_speed": r.get("i2_speed"),
                "st_speed": r.get("st_speed"),
                "segments_sector_1": r.get("segments_sector_1") or None,
                "segments_sector_2": r.get("segments_sector_2") or None,
                "segments_sector_3": r.get("segments_sector_3") or None,
                "is_pit_out_lap": r.get("is_pit_out_lap", False),
                "date_start": _parse_dt(r.get("date_start")),
            }
            for r in raw
        ]
        await self._bulk_insert(Lap, records)
        logger.info("Ingested %d laps for session %d", len(records), session_key)

    async def _ingest_stints(self, session_key: int, session_id: int) -> None:
        count = await self._count_rows(Stint, session_id)
        if count > 0:
            return

        raw = await self._client.get_stints(session_key)
        records = [
            {
                "session_id": session_id,
                "driver_number": r.get("driver_number"),
                "stint_number": r.get("stint_number"),
                "compound": r.get("compound", "MEDIUM"),
                "lap_start": r.get("lap_start", 1),
                "lap_end": r.get("lap_end"),
                "tyre_age_at_start": r.get("tyre_age_at_start", 0),
            }
            for r in raw
        ]
        await self._bulk_insert(Stint, records)
        logger.info("Ingested %d stints for session %d", len(records), session_key)

    async def _ingest_race_control(self, session_key: int, session_id: int) -> None:
        count = await self._count_rows(RaceControlEvent, session_id)
        if count > 0:
            return

        raw = await self._client.get_race_control(session_key)
        records = [
            {
                "session_id": session_id,
                "timestamp": _parse_dt(r.get("date")),
                "category": r.get("category", "Other"),
                "flag": r.get("flag"),
                "scope": r.get("scope"),
                "sector": r.get("sector"),
                "driver_number": r.get("driver_number"),
                "lap_number": r.get("lap_number"),
                "message": r.get("message", ""),
            }
            for r in raw
        ]
        await self._bulk_insert(RaceControlEvent, records)
        logger.info("Ingested %d race control events for session %d", len(records), session_key)

    async def _ingest_intervals(self, session_key: int, session_id: int) -> None:
        count = await self._count_rows(Interval, session_id)
        if count > 0:
            return

        raw = await self._client.get_intervals(session_key)
        records = [
            {
                "session_id": session_id,
                "driver_number": r.get("driver_number"),
                "timestamp": _parse_dt(r.get("date")),
                "gap_to_leader": r.get("gap_to_leader"),
                "interval_ahead": r.get("interval"),
            }
            for r in raw
        ]
        await self._bulk_insert(Interval, records)
        logger.info("Ingested %d intervals for session %d", len(records), session_key)

    async def _ingest_positions(self, session_key: int, session_id: int) -> None:
        count = await self._count_rows(Position, session_id)
        if count > 0:
            return

        raw = await self._client.get_positions(session_key)
        records = [
            {
                "session_id": session_id,
                "driver_number": r.get("driver_number"),
                "timestamp": _parse_dt(r.get("date")),
                "position": r.get("position", 0),
            }
            for r in raw
        ]
        await self._bulk_insert(Position, records)
        logger.info("Ingested %d positions for session %d", len(records), session_key)

    async def _ingest_pit_stops(self, session_key: int, session_id: int) -> None:
        count = await self._count_rows(PitStop, session_id)
        if count > 0:
            return

        raw = await self._client.get_pit_stops(session_key)
        records = [
            {
                "session_id": session_id,
                "driver_number": r.get("driver_number"),
                "timestamp": _parse_dt(r.get("date")),
                "lap_number": r.get("lap_number", 0),
                "pit_duration": r.get("pit_duration"),
                "stop_duration": r.get("stop_duration"),
            }
            for r in raw
        ]
        await self._bulk_insert(PitStop, records)
        logger.info("Ingested %d pit stops for session %d", len(records), session_key)

    # --- Helpers ---

    async def _get_session_id(self, session_key: int) -> int:
        """Get internal session ID from session_key."""
        result = await self._db.execute(
            select(Session.id).where(Session.session_key == session_key)
        )
        session_id = result.scalar_one_or_none()
        if session_id is None:
            raise ValueError(f"Session with key {session_key} not found in database")
        return session_id

    async def _count_rows(self, model_class, session_id: int) -> int:
        """Count existing rows for a model in a given session."""
        result = await self._db.execute(
            select(func.count()).select_from(model_class).where(
                model_class.session_id == session_id
            )
        )
        return result.scalar_one()

    async def _update_session_status(self, session_key: int, status: str) -> None:
        """Update ingest_status on the sessions table."""
        values = {"ingest_status": status}
        if status == "complete":
            values["ingested_at"] = datetime.utcnow()
        await self._db.execute(
            update(Session).where(Session.session_key == session_key).values(**values)
        )
        await self._db.commit()

    async def _bulk_insert(
        self, model_class, records: list[dict], batch_size: int = 10000
    ) -> None:
        """Insert records in batches for memory efficiency."""
        if not records:
            return
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            await self._db.execute(insert(model_class), batch)
            await self._db.commit()
