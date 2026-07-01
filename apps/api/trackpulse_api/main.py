from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .middleware import RequestContextMiddleware
from .observability import configure_logging
from .routes.health import router as health_router
from .routes.openf1 import router as openf1_router
from .routes.version import router as version_router
from .settings import AppSettings, get_settings


def create_app(settings: AppSettings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    app = FastAPI(title=app_settings.app_name, version=app_settings.app_version)
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
    app.include_router(version_router)
    return app


app = create_app()
