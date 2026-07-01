from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..settings import AppSettings


def create_engine_from_settings(settings: AppSettings) -> AsyncEngine:
    return create_async_engine(
        settings.db_url,
        pool_pre_ping=True,
        future=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def check_database_ready(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    async with session_factory() as session:
        await session.execute(text("SELECT 1"))
    return True


async def get_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
