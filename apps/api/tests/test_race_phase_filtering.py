"""Tests for race phase filtering — timeline start trimming and race_start metadata."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from trackpulse_api.db.base import Base
from trackpulse_api.db.models.car_position import CarPosition
from trackpulse_api.db.models.car_telemetry import CarTelemetry
from trackpulse_api.db.models.car_timeline import CarTimeline
from trackpulse_api.db.models.driver import Driver
from trackpulse_api.db.models.lap import Lap
from trackpulse_api.db.models.meeting import Meeting
from trackpulse_api.db.models.position import Position
from trackpulse_api.db.models.race_control_event import RaceControlEvent
from trackpulse_api.db.models.session import Session
from trackpulse_api.services.timeline_service import TimelineService, _FORMATION_LAP_OFFSET_SECONDS

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# Make PostgreSQL-specific types render as compatible types in SQLite
@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"

# Timestamps simulating a real race session:
# Position data starts 1 hour before race start (reconnaissance laps + grid)
T_FIRST_POSITION = datetime(2024, 3, 2, 14, 0, 0, tzinfo=timezone.utc)
T_RACE_START = datetime(2024, 3, 2, 15, 0, 0, tzinfo=timezone.utc)
T_RACE_END = datetime(2024, 3, 2, 16, 30, 0, tzinfo=timezone.utc)
T_FORMATION_LAP = T_RACE_START - timedelta(seconds=_FORMATION_LAP_OFFSET_SECONDS)


@pytest.fixture
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def seeded_db(db_session: AsyncSession):
    """Seed database with a race session including pre-race position data."""
    # Meeting
    meeting = Meeting(
        id=1, meeting_key=1234, meeting_name="Bahrain GP",
        country_name="Bahrain", location="Sakhir", circuit_short_name="bahrain",
        year=2024, date_start=T_RACE_START,
    )
    db_session.add(meeting)

    # Session (Race type)
    session = Session(
        id=1,
        session_key=9472,
        meeting_id=1,
        session_name="Race",
        session_type="Race",
        date_start=T_RACE_START,
    )
    db_session.add(session)

    # Drivers
    for dn in [1, 16]:
        db_session.add(Driver(
            session_id=1,
            driver_number=dn,
            full_name=f"Driver {dn}",
            name_acronym=f"D{dn:02d}",
            team_name="Team A",
            team_colour="FFFFFF",
        ))

    # Race control: SESSION STARTED event
    db_session.add(RaceControlEvent(
        session_id=1,
        timestamp=T_RACE_START,
        category="SessionStatus",
        message="SESSION STARTED",
    ))
    db_session.add(RaceControlEvent(
        session_id=1,
        timestamp=T_RACE_END,
        category="SessionStatus",
        message="SESSION FINISHED",
    ))

    # Position data: starts 1 hour before race (simulating pre-race)
    # We generate sparse samples: every 60s during pre-race, every 1s during race
    for dn in [1, 16]:
        # Pre-race: 60 samples (1 per minute for 1 hour)
        for i in range(60):
            ts = T_FIRST_POSITION + timedelta(minutes=i)
            db_session.add(CarPosition(
                session_id=1,
                driver_number=dn,
                timestamp=ts,
                x=float(dn * 10),
                y=float(dn * 5),
            ))
        # During race: 30 samples starting from formation lap
        for i in range(30):
            ts = T_FORMATION_LAP + timedelta(seconds=i * 10)
            db_session.add(CarPosition(
                session_id=1,
                driver_number=dn,
                timestamp=ts,
                x=float(100 + i * 10 + dn),
                y=float(50 + i * 5 + dn),
            ))

    # Telemetry: same pattern
    for dn in [1, 16]:
        # Pre-race: stationary
        for i in range(60):
            ts = T_FIRST_POSITION + timedelta(minutes=i)
            db_session.add(CarTelemetry(
                session_id=1,
                driver_number=dn,
                timestamp=ts,
                speed=0,
            ))
        # Race: moving
        for i in range(30):
            ts = T_FORMATION_LAP + timedelta(seconds=i * 10)
            db_session.add(CarTelemetry(
                session_id=1,
                driver_number=dn,
                timestamp=ts,
                speed=200 + i,
            ))

    # Laps: lap 1 starts at race start
    for dn in [1, 16]:
        db_session.add(Lap(
            session_id=1,
            driver_number=dn,
            lap_number=1,
            date_start=T_RACE_START,
        ))
        db_session.add(Lap(
            session_id=1,
            driver_number=dn,
            lap_number=2,
            date_start=T_RACE_START + timedelta(seconds=90),
        ))

    # Positions (race standings)
    for dn in [1, 16]:
        for i in range(30):
            ts = T_FORMATION_LAP + timedelta(seconds=i * 10)
            db_session.add(Position(
                session_id=1,
                driver_number=dn,
                timestamp=ts,
                position=dn,
            ))

    await db_session.commit()
    return session


@pytest.mark.asyncio
async def test_get_race_start_timestamp(db_session, seeded_db):
    """_get_race_start_timestamp returns the SESSION STARTED event time."""
    service = TimelineService(db_session)
    ts = await service._get_race_start_timestamp(session_id=1)
    # SQLite returns naive datetimes — compare without timezone
    assert ts.replace(tzinfo=None) == T_RACE_START.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_get_race_start_timestamp_missing(db_session, engine):
    """Returns None when no SESSION STARTED event exists."""
    meeting = Meeting(
        id=2, meeting_key=5555, meeting_name="Test GP",
        country_name="Test", location="Test", circuit_short_name="test",
        year=2024, date_start=T_RACE_START,
    )
    db_session.add(meeting)
    session = Session(
        id=2, session_key=5555, meeting_id=2,
        session_name="Practice 1", session_type="Practice",
        date_start=T_RACE_START,
    )
    db_session.add(session)
    await db_session.commit()

    service = TimelineService(db_session)
    ts = await service._get_race_start_timestamp(session_id=2)
    assert ts is None


@pytest.mark.asyncio
async def test_get_effective_start_race_session(db_session, seeded_db):
    """For Race sessions, effective start is race_start minus formation offset."""
    service = TimelineService(db_session)
    effective = await service._get_effective_start(seeded_db)
    # SQLite returns naive datetimes — compare without timezone
    assert effective.replace(tzinfo=None) == T_FORMATION_LAP.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_get_effective_start_practice_session(db_session, engine):
    """For non-Race sessions, effective start is None (use all data)."""
    meeting = Meeting(
        id=3, meeting_key=6666, meeting_name="Test GP",
        country_name="Test", location="Test", circuit_short_name="test",
        year=2024, date_start=T_RACE_START,
    )
    db_session.add(meeting)
    practice = Session(
        id=3, session_key=6666, meeting_id=3,
        session_name="Practice 1", session_type="Practice",
        date_start=T_RACE_START,
    )
    db_session.add(practice)
    await db_session.commit()

    service = TimelineService(db_session)
    effective = await service._get_effective_start(practice)
    assert effective is None


@pytest.mark.asyncio
async def test_build_timeline_filters_pre_race_data(db_session, seeded_db):
    """Building timeline for Race session should start from formation lap, not first position."""
    service = TimelineService(db_session)
    timeline = await service._build_timeline(session_id=1, target_hz=1.0, session=seeded_db)

    assert len(timeline) > 0

    # The first frame should be at or after the formation lap start
    first_ts = datetime.fromisoformat(timeline[0].timestamp).replace(tzinfo=None)
    assert first_ts >= T_FORMATION_LAP.replace(tzinfo=None)

    # The first frame should NOT be at the original first position time
    assert first_ts > T_FIRST_POSITION.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_build_timeline_without_session_uses_all_data(db_session, seeded_db):
    """Building timeline without session arg (backwards compat) uses all position data."""
    service = TimelineService(db_session)
    timeline = await service._build_timeline(session_id=1, target_hz=1.0, session=None)

    first_ts = datetime.fromisoformat(timeline[0].timestamp).replace(tzinfo=None)
    # Should start from the very first position (pre-race)
    assert first_ts <= T_FIRST_POSITION.replace(tzinfo=None) + timedelta(seconds=1)


@pytest.mark.asyncio
async def test_timeline_meta_includes_race_start_elapsed(db_session, seeded_db):
    """get_timeline_meta returns race_start_elapsed_seconds for Race sessions."""
    # We need to store a pre-computed timeline first for meta to read
    service = TimelineService(db_session)
    timeline = await service._build_timeline(session_id=1, target_hz=1.0, session=seeded_db)
    await service._store_timeline(session_id=1, timeline=timeline)

    meta = await service.get_timeline_meta(session_key=9472, target_hz=1.0, chunk_seconds=120.0)

    # race_start_elapsed_seconds should be approximately _FORMATION_LAP_OFFSET_SECONDS
    # (since timeline starts at formation lap, and race starts offset seconds later)
    assert meta["race_start_elapsed_seconds"] is not None
    assert meta["race_start_elapsed_seconds"] == pytest.approx(
        _FORMATION_LAP_OFFSET_SECONDS, abs=2.0
    )


@pytest.mark.asyncio
async def test_compact_chunk_includes_race_start_elapsed(db_session, seeded_db):
    """get_compact_chunk returns race_start_elapsed_seconds."""
    service = TimelineService(db_session)
    timeline = await service._build_timeline(session_id=1, target_hz=1.0, session=seeded_db)
    await service._store_timeline(session_id=1, timeline=timeline)

    chunk = await service.get_compact_chunk(
        session_key=9472, chunk_index=0, chunk_seconds=120.0, target_hz=1.0,
    )

    assert chunk is not None
    assert chunk["race_start_elapsed_seconds"] is not None
    assert chunk["race_start_elapsed_seconds"] == pytest.approx(
        _FORMATION_LAP_OFFSET_SECONDS, abs=2.0
    )
