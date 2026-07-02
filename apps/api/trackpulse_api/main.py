from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from trackpulse_api.config import Settings
from trackpulse_api.db.engine import create_engine, create_session_factory
from trackpulse_api.routes.circuit import router as circuit_router
from trackpulse_api.routes.health import router as health_router
from trackpulse_api.routes.ingest import router as ingest_router
from trackpulse_api.routes.sessions import router as sessions_router
from trackpulse_api.routes.timeline import router as timeline_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — initialize DB engine and session factory
    settings: Settings = app.state.settings
    engine = create_engine(settings.database_url)
    app.state.db_engine = engine
    app.state.db_session_factory = create_session_factory(engine)
    yield
    # Shutdown — dispose engine
    await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    app.state.settings = settings

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(circuit_router)
    app.include_router(ingest_router)
    app.include_router(timeline_router)

    return app


app = create_app()
