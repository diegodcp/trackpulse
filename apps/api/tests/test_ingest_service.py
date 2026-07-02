from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, event, Text, BigInteger
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from trackpulse_api.clients.openf1 import OpenF1UnavailableError
from trackpulse_api.db.base import Base
from trackpulse_api.db.models.car_position import CarPosition
from trackpulse_api.db.models.car_telemetry import CarTelemetry
from trackpulse_api.db.models.driver import Driver
from trackpulse_api.db.models.interval import Interval
from trackpulse_api.db.models.lap import Lap
from trackpulse_api.db.models.meeting import Meeting
from trackpulse_api.db.models.pit_stop import PitStop
from trackpulse_api.db.models.position import Position
from trackpulse_api.db.models.race_control_event import RaceControlEvent
from trackpulse_api.db.models.session import Session
from trackpulse_api.db.models.stint import Stint
from trackpulse_api.db.models.weather_sample import WeatherSample
from trackpulse_api.services.ingest_service import IngestService


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

TEST_SESSION_KEY = 9472


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def session_in_db(db_session):
    """Create a meeting and session in the DB."""
    meeting = Meeting(
        meeting_key=1234,
        meeting_name="Test GP",
        country_name="Test",
        location="Test Circuit",
        circuit_short_name="TST",
        year=2024,
        date_start=datetime(2024, 3, 1),
    )
    db_session.add(meeting)
    await db_session.flush()

    session = Session(
        session_key=TEST_SESSION_KEY,
        meeting_id=meeting.id,
        session_name="Race",
        session_type="Race",
        date_start=datetime(2024, 3, 2),
        ingest_status="pending",
    )
    db_session.add(session)
    await db_session.commit()
    return session


@pytest.fixture
def mock_client():
    """Create a mock OpenF1 client with all methods."""
    client = AsyncMock()
    client.get_drivers.return_value = [
        {
            "driver_number": 1,
            "full_name": "Max VERSTAPPEN",
            "name_acronym": "VER",
            "team_name": "Red Bull Racing",
            "team_colour": "3671C6",
            "headshot_url": "https://example.com/ver.png",
        },
        {
            "driver_number": 16,
            "full_name": "Charles LECLERC",
            "name_acronym": "LEC",
            "team_name": "Ferrari",
            "team_colour": "E80020",
            "headshot_url": "https://example.com/lec.png",
        },
    ]
    client.get_weather.return_value = [
        {
            "date": "2024-03-02T15:00:00+00:00",
            "air_temperature": 28.5,
            "track_temperature": 45.2,
            "humidity": 42.0,
            "pressure": 1013.0,
            "wind_speed": 3.2,
            "wind_direction": 180,
            "rainfall": False,
        }
    ]
    client.get_location.return_value = [
        {
            "driver_number": 1,
            "date": "2024-03-02T15:00:00+00:00",
            "x": 1234.5,
            "y": 6789.0,
            "z": 10.0,
        }
    ]
    client.get_car_data.return_value = [
        {
            "driver_number": 1,
            "date": "2024-03-02T15:00:00+00:00",
            "speed": 320,
            "throttle": 100,
            "brake": 0,
            "n_gear": 8,
            "rpm": 11500,
            "drs": 12,
        }
    ]
    client.get_laps.return_value = [
        {
            "driver_number": 1,
            "lap_number": 1,
            "lap_duration": 92.5,
            "duration_sector_1": 28.1,
            "duration_sector_2": 35.2,
            "duration_sector_3": 29.2,
            "i1_speed": 310,
            "i2_speed": 295,
            "st_speed": 320,
            "is_pit_out_lap": False,
            "date_start": "2024-03-02T15:01:00+00:00",
        }
    ]
    client.get_stints.return_value = [
        {
            "driver_number": 1,
            "stint_number": 1,
            "compound": "MEDIUM",
            "lap_start": 1,
            "lap_end": 20,
            "tyre_age_at_start": 0,
        }
    ]
    client.get_race_control.return_value = [
        {
            "date": "2024-03-02T15:00:00+00:00",
            "category": "Flag",
            "flag": "GREEN",
            "scope": "Track",
            "message": "GREEN LIGHT - PIT EXIT OPEN",
        }
    ]
    client.get_intervals.return_value = [
        {
            "driver_number": 1,
            "date": "2024-03-02T15:00:00+00:00",
            "gap_to_leader": 0.0,
            "interval": None,
        }
    ]
    client.get_positions.return_value = [
        {
            "driver_number": 1,
            "date": "2024-03-02T15:00:00+00:00",
            "position": 1,
        }
    ]
    client.get_pit_stops.return_value = [
        {
            "driver_number": 1,
            "date": "2024-03-02T15:10:00+00:00",
            "lap_number": 15,
            "pit_duration": 22.5,
            "stop_duration": 2.3,
        }
    ]
    return client


class TestIngestService:
    @pytest.mark.asyncio
    async def test_full_ingest_happy_path(self, mock_client, db_session, session_in_db):
        """All stages complete successfully and status is 'complete'."""
        service = IngestService(mock_client, db_session)
        await service.start_ingest(session_key=TEST_SESSION_KEY)

        # Verify all client methods called
        mock_client.get_drivers.assert_called_once_with(TEST_SESSION_KEY)
        # location and car_data are called per-driver (2 drivers in fixture)
        assert mock_client.get_location.call_count == 2
        mock_client.get_location.assert_any_call(TEST_SESSION_KEY, driver_number=1)
        mock_client.get_location.assert_any_call(TEST_SESSION_KEY, driver_number=16)
        assert mock_client.get_car_data.call_count == 2
        mock_client.get_car_data.assert_any_call(TEST_SESSION_KEY, driver_number=1)
        mock_client.get_car_data.assert_any_call(TEST_SESSION_KEY, driver_number=16)
        mock_client.get_weather.assert_called_once_with(TEST_SESSION_KEY)
        mock_client.get_laps.assert_called_once_with(TEST_SESSION_KEY)
        mock_client.get_stints.assert_called_once_with(TEST_SESSION_KEY)
        mock_client.get_race_control.assert_called_once_with(TEST_SESSION_KEY)
        mock_client.get_intervals.assert_called_once_with(TEST_SESSION_KEY)
        mock_client.get_positions.assert_called_once_with(TEST_SESSION_KEY)
        mock_client.get_pit_stops.assert_called_once_with(TEST_SESSION_KEY)

        # Verify session status updated to 'complete'
        result = await db_session.execute(
            select(Session.ingest_status).where(Session.session_key == TEST_SESSION_KEY)
        )
        assert result.scalar_one() == "complete"

    @pytest.mark.asyncio
    async def test_idempotent_skip_completed_stages(self, mock_client, db_session, session_in_db):
        """Re-running ingest skips already-completed stages."""
        # Pre-populate weather data
        from sqlalchemy import insert

        await db_session.execute(
            insert(WeatherSample),
            [
                {
                    "session_id": session_in_db.id,
                    "timestamp": datetime(2024, 3, 2, 15, 0, 0),
                    "air_temperature": 28.5,
                    "track_temperature": 45.2,
                    "humidity": 42.0,
                    "pressure": 1013.0,
                    "wind_speed": 3.2,
                    "wind_direction": 180,
                    "rainfall": False,
                }
            ],
        )
        await db_session.commit()

        service = IngestService(mock_client, db_session)
        await service.start_ingest(session_key=TEST_SESSION_KEY)

        # Weather should not have been fetched
        mock_client.get_weather.assert_not_called()
        # Other stages should still be called
        mock_client.get_drivers.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_failure_marks_failed(self, mock_client, db_session, session_in_db):
        """If one stage fails, session status is 'failed'."""
        mock_client.get_location.side_effect = OpenF1UnavailableError("timeout")

        service = IngestService(mock_client, db_session)
        with pytest.raises(OpenF1UnavailableError):
            await service.start_ingest(session_key=TEST_SESSION_KEY)

        # Status should be 'failed'
        result = await db_session.execute(
            select(Session.ingest_status).where(Session.session_key == TEST_SESSION_KEY)
        )
        assert result.scalar_one() == "failed"

    @pytest.mark.asyncio
    async def test_drivers_fetched_first(self, mock_client, db_session, session_in_db):
        """Drivers stage completes before other stages start."""
        call_order = []

        async def track_drivers(key):
            call_order.append("drivers")
            return [
                {
                    "driver_number": 1,
                    "full_name": "Max VERSTAPPEN",
                    "name_acronym": "VER",
                    "team_name": "Red Bull Racing",
                    "team_colour": "3671C6",
                }
            ]

        async def track_weather(key):
            call_order.append("weather")
            return []

        async def track_laps(key):
            call_order.append("laps")
            return []

        mock_client.get_drivers.side_effect = track_drivers
        mock_client.get_weather.side_effect = track_weather
        mock_client.get_laps.side_effect = track_laps
        mock_client.get_stints.return_value = []
        mock_client.get_race_control.return_value = []
        mock_client.get_pit_stops.return_value = []
        mock_client.get_location.return_value = []
        mock_client.get_car_data.return_value = []
        mock_client.get_intervals.return_value = []
        mock_client.get_positions.return_value = []

        service = IngestService(mock_client, db_session)
        await service.start_ingest(session_key=TEST_SESSION_KEY)

        assert call_order.index("drivers") < call_order.index("weather")

    @pytest.mark.asyncio
    async def test_session_not_found_raises(self, mock_client, db_session):
        """Ingest raises ValueError if session doesn't exist."""
        service = IngestService(mock_client, db_session)
        with pytest.raises(ValueError, match="not found"):
            await service.start_ingest(session_key=99999)

    @pytest.mark.asyncio
    async def test_get_progress_pending(self, mock_client, db_session, session_in_db):
        """Progress returns pending before ingest starts."""
        service = IngestService(mock_client, db_session)
        progress = await service.get_progress(TEST_SESSION_KEY)

        assert progress["status"] == "pending"
        assert progress["session_key"] == TEST_SESSION_KEY
        assert len(progress["stages_remaining"]) == 10
        assert len(progress["stages_complete"]) == 0

    @pytest.mark.asyncio
    async def test_get_progress_after_ingest(self, mock_client, db_session, session_in_db):
        """Progress returns complete with row counts after ingest."""
        service = IngestService(mock_client, db_session)
        await service.start_ingest(session_key=TEST_SESSION_KEY)
        progress = await service.get_progress(TEST_SESSION_KEY)

        assert progress["status"] == "complete"
        assert progress["rows_ingested"]["drivers"] == 2
        assert progress["rows_ingested"]["weather"] == 1
        assert progress["rows_ingested"]["location"] == 2
