from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from trackpulse_api.config import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session from the app-level session factory."""
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        yield session
