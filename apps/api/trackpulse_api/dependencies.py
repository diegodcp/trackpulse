from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from trackpulse_api.clients.openf1 import OpenF1Client
from trackpulse_api.config import Settings
from trackpulse_api.services.circuit_service import CircuitService
from trackpulse_api.services.ingest_service import IngestService
from trackpulse_api.services.session_discovery import SessionDiscoveryService
from trackpulse_api.services.timeline_service import TimelineService


@lru_cache
def get_settings() -> Settings:
    return Settings()


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session from the app-level session factory."""
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        yield session


def get_openf1_client(request: Request) -> OpenF1Client:
    settings: Settings = request.app.state.settings
    return OpenF1Client(base_url=settings.openf1_base_url)


async def get_session_discovery_service(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> SessionDiscoveryService:
    client = get_openf1_client(request)
    return SessionDiscoveryService(openf1_client=client, db_session=db_session)


async def get_circuit_service(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> CircuitService:
    client = get_openf1_client(request)
    return CircuitService(openf1_client=client, db_session=db_session)


async def get_ingest_service(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> IngestService:
    client = get_openf1_client(request)
    return IngestService(openf1_client=client, db_session=db_session)


async def get_timeline_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> TimelineService:
    return TimelineService(db_session=db_session)
