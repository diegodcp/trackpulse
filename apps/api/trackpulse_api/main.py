from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .db.session import create_engine_from_settings, create_session_factory
from .middleware import RequestContextMiddleware
from .observability import configure_logging
from .replay.controller import FixtureReplayController
from .routes.health import router as health_router
from .routes.openf1 import router as openf1_router
from .routes.replay import router as replay_router
from .routes.version import router as version_router
from .settings import AppSettings, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_engine: AsyncEngine | None = None
    db_session_factory: async_sessionmaker[AsyncSession] | None = None
    replay_controller = FixtureReplayController(app.state.settings)

    if app.state.settings.db_enabled:
        db_engine = create_engine_from_settings(app.state.settings)
        db_session_factory = create_session_factory(db_engine)

    app.state.db_engine = db_engine
    app.state.db_session_factory = db_session_factory
    app.state.replay_controller = replay_controller

    try:
        yield
    finally:
        await replay_controller.shutdown()
        if db_engine is not None:
            await db_engine.dispose()


def create_app(settings: AppSettings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    app = FastAPI(title=app_settings.app_name, version=app_settings.app_version, lifespan=lifespan)
    app.state.settings = app_settings

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_allow_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(openf1_router)
    app.include_router(replay_router)
    app.include_router(version_router)
    return app


app = create_app()
