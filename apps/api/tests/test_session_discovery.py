import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from trackpulse_api.db.base import Base
from trackpulse_api.db.models.meeting import Meeting
from trackpulse_api.db.models.session import Session as SessionModel
from trackpulse_api.services.session_discovery import SessionDiscoveryService


MOCK_MEETINGS = [
    {
        "meeting_key": 1219,
        "meeting_name": "Bahrain Grand Prix",
        "country_name": "Bahrain",
        "location": "Sakhir",
        "circuit_short_name": "Bahrain",
        "circuit_key": 63,
        "year": 2023,
        "date_start": "2023-03-03T00:00:00+00:00",
        "gmt_offset": "+03:00",
    }
]

MOCK_SESSIONS = [
    {
        "session_key": 9158,
        "session_name": "Race",
        "session_type": "Race",
        "date_start": "2023-03-05T15:00:00+00:00",
        "date_end": "2023-03-05T17:00:00+00:00",
    },
    {
        "session_key": 9155,
        "session_name": "Practice 1",
        "session_type": "Practice",
        "date_start": "2023-03-03T11:30:00+00:00",
        "date_end": "2023-03-03T12:30:00+00:00",
    },
]


@pytest.fixture
async def db_session_for_service():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Meeting.__table__.create(sync_conn, checkfirst=True)
        )
        await conn.run_sync(
            lambda sync_conn: SessionModel.__table__.create(sync_conn, checkfirst=True)
        )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get_meetings = AsyncMock(return_value=MOCK_MEETINGS)
    client.get_sessions = AsyncMock(return_value=MOCK_SESSIONS)
    return client


@pytest.mark.asyncio
async def test_fetches_from_openf1_on_first_call(mock_client, db_session_for_service):
    """First call fetches from OpenF1 and caches in DB."""
    service = SessionDiscoveryService(mock_client, db_session_for_service)
    result = await service.get_sessions_by_year(2023)
    assert len(result) == 1
    assert result[0].meeting_name == "Bahrain Grand Prix"
    assert len(result[0].sessions) == 2
    mock_client.get_meetings.assert_called_once_with(2023, None)


@pytest.mark.asyncio
async def test_serves_from_cache_on_second_call(mock_client, db_session_for_service):
    """Second call serves from DB without hitting OpenF1."""
    service = SessionDiscoveryService(mock_client, db_session_for_service)
    await service.get_sessions_by_year(2023)
    await service.get_sessions_by_year(2023)
    # Only called once (first time)
    mock_client.get_meetings.assert_called_once()


@pytest.mark.asyncio
async def test_country_filter(mock_client, db_session_for_service):
    """Country filter is passed to client and filters results."""
    service = SessionDiscoveryService(mock_client, db_session_for_service)
    result = await service.get_sessions_by_year(2023, country="Bahrain")
    mock_client.get_meetings.assert_called_once_with(2023, "Bahrain")
    assert len(result) == 1
    assert result[0].country_name == "Bahrain"


@pytest.mark.asyncio
async def test_empty_result_from_openf1(db_session_for_service):
    """Returns empty list when OpenF1 returns no meetings."""
    client = AsyncMock()
    client.get_meetings = AsyncMock(return_value=[])
    service = SessionDiscoveryService(client, db_session_for_service)
    result = await service.get_sessions_by_year(2023)
    assert result == []
