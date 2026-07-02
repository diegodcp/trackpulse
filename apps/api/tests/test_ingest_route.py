from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from trackpulse_api.config import Settings
from trackpulse_api.db.base import Base
from trackpulse_api.db.models.meeting import Meeting
from trackpulse_api.db.models.session import Session
from trackpulse_api.dependencies import get_ingest_service
from trackpulse_api.main import create_app
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
def mock_ingest_service(engine):
    """Mock IngestService for route tests."""
    service = AsyncMock(spec=IngestService)

    async def _get_session_id(session_key):
        if session_key == TEST_SESSION_KEY:
            return 1
        raise ValueError(f"Session with key {session_key} not found in database")

    service._get_session_id = AsyncMock(side_effect=_get_session_id)
    service.start_ingest = AsyncMock(return_value=None)

    async def _get_progress(session_key):
        if session_key != TEST_SESSION_KEY:
            raise ValueError(f"Session with key {session_key} not found in database")
        return {
            "session_key": TEST_SESSION_KEY,
            "status": "pending",
            "stages_complete": [],
            "stages_remaining": [
                "drivers", "weather", "location", "car_data", "laps",
                "stints", "race_control", "intervals", "positions", "pit_stops",
            ],
            "rows_ingested": {
                "drivers": 0, "weather": 0, "location": 0, "car_data": 0,
                "laps": 0, "stints": 0, "race_control": 0, "intervals": 0,
                "positions": 0, "pit_stops": 0,
            },
        }

    service.get_progress = AsyncMock(side_effect=_get_progress)
    return service


@pytest.fixture
def app(engine, mock_ingest_service):
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    application = create_app(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    application.state.db_session_factory = session_factory
    application.state.db_engine = engine

    application.dependency_overrides[get_ingest_service] = lambda: mock_ingest_service
    return application


@pytest.fixture
async def session_in_db(engine):
    """Seed a meeting + session into the test database."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
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


@pytest.fixture
async def async_client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


class TestIngestRoute:
    @pytest.mark.asyncio
    async def test_trigger_ingest_returns_202(self, async_client, session_in_db):
        """POST /ingest returns 202 Accepted immediately."""
        response = await async_client.post(
            f"/api/v1/sessions/{TEST_SESSION_KEY}/ingest"
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["session_key"] == TEST_SESSION_KEY

    @pytest.mark.asyncio
    async def test_trigger_ingest_session_not_found(self, async_client):
        """POST /ingest returns 404 for unknown session."""
        response = await async_client.post("/api/v1/sessions/99999/ingest")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_ingest_status_pending(self, async_client, session_in_db):
        """Status returns pending before ingest starts."""
        response = await async_client.get(
            f"/api/v1/sessions/{TEST_SESSION_KEY}/ingest/status"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["session_key"] == TEST_SESSION_KEY
        assert len(data["stages_remaining"]) == 10
        assert len(data["stages_complete"]) == 0

    @pytest.mark.asyncio
    async def test_ingest_status_session_not_found(self, async_client):
        """Status returns 404 for unknown session."""
        response = await async_client.get("/api/v1/sessions/99999/ingest/status")
        assert response.status_code == 404
