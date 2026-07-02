import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from trackpulse_api.config import Settings
from trackpulse_api.main import create_app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def settings():
    return Settings(database_url=TEST_DATABASE_URL)


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
async def async_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine):
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def async_client(app, async_engine):
    """Async test client with DB session factory attached to app state."""
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    app.state.db_session_factory = session_factory
    app.state.db_engine = async_engine
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
