from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from trackpulse_api.clients.openf1 import OpenF1ClientProtocol
from trackpulse_api.db.models.meeting import Meeting
from trackpulse_api.db.models.session import Session as SessionModel
from trackpulse_api.schemas.sessions import MeetingWithSessions, SessionInfo


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO datetime string from OpenF1 into a Python datetime."""
    if not value:
        return None
    return datetime.fromisoformat(value)


class SessionDiscoveryService:
    """Discovers sessions, caches in DB, returns from cache on subsequent calls."""

    def __init__(self, openf1_client: OpenF1ClientProtocol, db_session: AsyncSession):
        self._client = openf1_client
        self._db = db_session

    async def get_sessions_by_year(
        self, year: int, country: str | None = None
    ) -> list[MeetingWithSessions]:
        # 1. Check DB for cached meetings for this year
        cached = await self._get_cached_meetings(year, country)
        if cached:
            return cached

        # 2. Fetch from OpenF1
        meetings_raw = await self._client.get_meetings(year, country)

        # 3. For each meeting, fetch sessions and store in DB
        for meeting_data in meetings_raw:
            meeting_key = meeting_data["meeting_key"]

            # Skip if already exists (race condition guard)
            existing = await self._db.execute(
                select(Meeting).where(Meeting.meeting_key == meeting_key)
            )
            if existing.scalar_one_or_none():
                continue

            meeting = Meeting(
                meeting_key=meeting_key,
                meeting_name=meeting_data.get("meeting_name", ""),
                country_name=meeting_data.get("country_name", ""),
                location=meeting_data.get("location", ""),
                circuit_short_name=meeting_data.get("circuit_short_name", ""),
                circuit_key=meeting_data.get("circuit_key"),
                year=meeting_data.get("year", year),
                date_start=_parse_dt(meeting_data.get("date_start")),
                gmt_offset=meeting_data.get("gmt_offset"),
            )
            self._db.add(meeting)
            await self._db.flush()

            # Fetch sessions for this meeting
            sessions_raw = await self._client.get_sessions(meeting_key)
            for session_data in sessions_raw:
                session = SessionModel(
                    session_key=session_data["session_key"],
                    meeting_id=meeting.id,
                    session_name=session_data.get("session_name", ""),
                    session_type=self._map_session_type(
                        session_data.get("session_type", "")
                    ),
                    date_start=_parse_dt(session_data.get("date_start")),
                    date_end=_parse_dt(session_data.get("date_end")),
                )
                self._db.add(session)

        await self._db.commit()

        # 4. Return from DB (now populated)
        return await self._get_cached_meetings(year, country)

    async def _get_cached_meetings(
        self, year: int, country: str | None = None
    ) -> list[MeetingWithSessions]:
        stmt = (
            select(Meeting)
            .options(selectinload(Meeting.sessions))
            .where(Meeting.year == year)
            .order_by(Meeting.date_start)
        )
        if country:
            stmt = stmt.where(Meeting.country_name.ilike(f"%{country}%"))

        result = await self._db.execute(stmt)
        meetings = result.scalars().all()

        if not meetings:
            return []

        return [
            MeetingWithSessions(
                meeting_key=m.meeting_key,
                meeting_name=m.meeting_name,
                country_name=m.country_name,
                location=m.location,
                circuit_short_name=m.circuit_short_name,
                year=m.year,
                date_start=m.date_start,
                sessions=[
                    SessionInfo(
                        session_key=s.session_key,
                        session_name=s.session_name,
                        session_type=s.session_type.value
                        if hasattr(s.session_type, "value")
                        else str(s.session_type),
                        date_start=s.date_start,
                        date_end=s.date_end,
                    )
                    for s in m.sessions
                ],
            )
            for m in meetings
        ]

    @staticmethod
    def _map_session_type(raw_type: str) -> str:
        """Map OpenF1 session_type string to our SessionType enum value."""
        mapping = {
            "Practice": "Practice",
            "Qualifying": "Qualifying",
            "Sprint": "Sprint",
            "Race": "Race",
            "Sprint Qualifying": "Qualifying",
            "Sprint Shootout": "Qualifying",
        }
        return mapping.get(raw_type, "Practice")
