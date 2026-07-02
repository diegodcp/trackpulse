"""Circuit geometry service — orchestrates fetch, extract, and store."""

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trackpulse_api.clients.openf1 import OpenF1ClientProtocol
from trackpulse_api.db.models.circuit_geometry import CircuitGeometry as CircuitGeometryModel
from trackpulse_api.db.models.session import Session as SessionModel
from trackpulse_api.processing.circuit_builder import (
    CircuitGeometry,
    CircuitPoint,
    CircuitSegment,
    extract_circuit_centerline,
)
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError


class CircuitService:
    """Orchestrates circuit geometry extraction: fetch data → build → store."""

    def __init__(self, openf1_client: OpenF1ClientProtocol, db_session: AsyncSession):
        self._client = openf1_client
        self._db = db_session

    async def get_or_build_circuit(self, session_key: int) -> CircuitGeometry:
        """Return cached circuit geometry or build from OpenF1 data."""
        # 1. Find session in DB
        result = await self._db.execute(
            select(SessionModel).where(SessionModel.session_key == session_key)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise SessionNotFoundError(f"Session with key {session_key} not found")

        # 2. Check DB cache
        existing = await self._get_from_db(session.id)
        if existing:
            return existing

        # 3. Fetch location data for a reference lap
        raw_positions, driver_number, lap_number = await self._fetch_reference_lap(session_key)

        # 4. Extract centerline (pure function)
        geometry = extract_circuit_centerline(
            raw_positions,
            source_driver=driver_number,
            source_lap=lap_number,
        )

        # 5. Store in DB
        await self._store_in_db(session.id, geometry)

        return geometry

    async def _get_from_db(self, session_id: int) -> CircuitGeometry | None:
        """Load cached geometry from DB, return None if not found."""
        result = await self._db.execute(
            select(CircuitGeometryModel).where(
                CircuitGeometryModel.session_id == session_id
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None

        points = [
            CircuitPoint(x=p["x"], y=p["y"], cumulative_dist=p["cumulative_dist"])
            for p in row.centerline
        ]
        segments = [
            CircuitSegment(
                id=s["id"],
                start_idx=s["start_idx"],
                end_idx=s["end_idx"],
                sector=s["sector"],
                start_dist=s["start_dist"],
                end_dist=s["end_dist"],
            )
            for s in row.segments
        ]
        return CircuitGeometry(
            points=points,
            segments=segments,
            bounds=row.bounds,
            total_length=row.total_length,
            source_driver=row.source_driver or 0,
            source_lap=row.source_lap or 0,
        )

    async def _fetch_reference_lap(self, session_key: int) -> tuple[list[dict], int, int]:
        """Fetch location data for a clean reference lap.

        Strategy: Find the fastest lap, then get location data for that driver/timespan.
        Returns (raw_positions, driver_number, lap_number).
        """
        # Get all laps to find the fastest one
        laps = await self._client.get_laps(session_key)

        # Filter to laps with valid duration (exclude pit laps, incomplete laps)
        valid_laps = [
            lap for lap in laps
            if lap.get("lap_duration") and lap["lap_duration"] > 0
            and not lap.get("is_pit_out_lap")
        ]

        if not valid_laps:
            raise InsufficientDataError(f"No valid laps found for session {session_key}")

        # Find fastest lap
        fastest = min(valid_laps, key=lambda l: l["lap_duration"])
        driver_number = fastest["driver_number"]
        lap_number = fastest["lap_number"]

        # Get location data for that driver during that lap
        date_start = fastest.get("date_start")
        # Estimate end time: start + duration
        date_end = None  # Let OpenF1 return all location for that driver if no end date

        raw_positions = await self._client.get_location(
            session_key=session_key,
            driver_number=driver_number,
            date_start=date_start,
            date_end=date_end,
        )

        if len(raw_positions) < 50:
            raise InsufficientDataError(
                f"Insufficient location data for driver {driver_number} "
                f"lap {lap_number}: got {len(raw_positions)} points"
            )

        return raw_positions, driver_number, lap_number

    async def _store_in_db(self, session_id: int, geometry: CircuitGeometry) -> None:
        """Persist circuit geometry to the database."""
        centerline_json = [asdict(p) for p in geometry.points]
        segments_json = [asdict(s) for s in geometry.segments]

        row = CircuitGeometryModel(
            session_id=session_id,
            total_points=len(geometry.points),
            centerline=centerline_json,
            segments=segments_json,
            bounds=geometry.bounds,
            total_length=geometry.total_length,
            source_driver=geometry.source_driver,
            source_lap=geometry.source_lap,
        )
        self._db.add(row)
        await self._db.commit()
