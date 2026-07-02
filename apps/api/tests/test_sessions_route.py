import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from trackpulse_api.clients.openf1 import OpenF1UnavailableError
from trackpulse_api.db.models.meeting import Meeting
from trackpulse_api.db.models.session import Session as SessionModel
from trackpulse_api.main import create_app
from trackpulse_api.config import Settings


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def settings():
    return Settings(database_url=TEST_DATABASE_URL)


@pytest.fixture
async def seeded_app(settings):
    """App with meetings pre-seeded in the database."""
    app = create_app(settings)
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Meeting.__table__.create(sync_conn, checkfirst=True)
        )
        await conn.run_sync(
            lambda sync_conn: SessionModel.__table__.create(sync_conn, checkfirst=True)
        )

    # Seed data
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        meeting = Meeting(
            meeting_key=1219,
            meeting_name="Bahrain Grand Prix",
            country_name="Bahrain",
            location="Sakhir",
            circuit_short_name="Bahrain",
            circuit_key=63,
            year=2023,
            date_start=datetime(2023, 3, 3, tzinfo=timezone.utc),
        )
        session.add(meeting)
        await session.flush()

        race = SessionModel(
            session_key=9158,
            meeting_id=meeting.id,
            session_name="Race",
            session_type="Race",
            date_start=datetime(2023, 3, 5, 15, 0, tzinfo=timezone.utc),
            date_end=datetime(2023, 3, 5, 17, 0, tzinfo=timezone.utc),
        )
        session.add(race)
        await session.commit()

    app.state.db_engine = engine
    app.state.db_session_factory = session_factory
    yield app
    await engine.dispose()


@pytest.fixture
async def seeded_client(seeded_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=seeded_app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_sessions_endpoint_returns_meetings(seeded_client):
    """GET /api/v1/sessions?year=2023 returns cached meetings."""
    response = await seeded_client.get("/api/v1/sessions?year=2023")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["meeting_name"] == "Bahrain Grand Prix"
    assert len(data[0]["sessions"]) == 1
    assert data[0]["sessions"][0]["session_name"] == "Race"


@pytest.mark.asyncio
async def test_sessions_endpoint_validates_year(seeded_client):
    """Year must be >= 2023."""
    response = await seeded_client.get("/api/v1/sessions?year=2020")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sessions_endpoint_validates_year_required(seeded_client):
    """Year parameter is required."""
    response = await seeded_client.get("/api/v1/sessions")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sessions_endpoint_country_filter(seeded_client):
    """Country filter works correctly."""
    response = await seeded_client.get("/api/v1/sessions?year=2023&country=Bahrain")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["country_name"] == "Bahrain"


@pytest.mark.asyncio
async def test_sessions_endpoint_country_filter_no_match(seeded_client):
    """Country filter with no match returns empty when OpenF1 also has nothing."""
    with patch(
        "trackpulse_api.clients.openf1.OpenF1Client.get_meetings",
        new_callable=AsyncMock,
        return_value=[],
    ):
        response = await seeded_client.get("/api/v1/sessions?year=2023&country=Narnia")
        assert response.status_code == 200
        data = response.json()
        assert data == []


@pytest.mark.asyncio
async def test_sessions_endpoint_openf1_unavailable(settings):
    """Returns 503 when OpenF1 is unreachable and no cache exists."""
    app = create_app(settings)
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Meeting.__table__.create(sync_conn, checkfirst=True)
        )
        await conn.run_sync(
            lambda sync_conn: SessionModel.__table__.create(sync_conn, checkfirst=True)
        )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch(
            "trackpulse_api.clients.openf1.OpenF1Client.get_meetings",
            new_callable=AsyncMock,
            side_effect=OpenF1UnavailableError("OpenF1 API is unavailable"),
        ):
            response = await client.get("/api/v1/sessions?year=2025")
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "openf1_unavailable"

    await engine.dispose()
