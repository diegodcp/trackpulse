from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import SQLAlchemyError

from ..observability import request_id_context
from ..db.session import check_database_ready, create_engine_from_settings, create_session_factory
from ..settings import AppSettings, get_app_settings

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live_health(settings: AppSettings = Depends(get_app_settings)) -> dict[str, object]:
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "openf1_mode": settings.openf1_mode,
        "request_id": request_id_context.get(),
    }


@router.get("/health/ready")
async def ready_health(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
) -> dict[str, object]:
    dependencies: dict[str, object] = {
        "openf1": {
            "mode": settings.openf1_mode,
            "ready": True,
        }
    }
    overall_ready = True

    if settings.db_enabled:
        db_dependency: dict[str, object] = {
            "enabled": True,
            "ready": False,
        }
        session_factory = getattr(request.app.state, "db_session_factory", None)
        if session_factory is None:
            db_engine = create_engine_from_settings(settings)
            session_factory = create_session_factory(db_engine)
            try:
                await check_database_ready(session_factory)
                db_dependency["ready"] = True
            except SQLAlchemyError as exc:
                db_dependency["error"] = str(exc.__class__.__name__)
                overall_ready = False
            finally:
                await db_engine.dispose()
        else:
            try:
                await check_database_ready(
                    session_factory,
                )
                db_dependency["ready"] = True
            except SQLAlchemyError as exc:
                db_dependency["error"] = str(exc.__class__.__name__)
                overall_ready = False

        dependencies["db"] = db_dependency

    return {
        "status": "ready" if overall_ready else "degraded",
        "ready": overall_ready,
        "app_name": settings.app_name,
        "dependencies": dependencies,
        "request_id": request_id_context.get(),
    }
