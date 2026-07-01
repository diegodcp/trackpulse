from fastapi import APIRouter, Depends

from ..observability import request_id_context
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
def ready_health(settings: AppSettings = Depends(get_app_settings)) -> dict[str, object]:
    return {
        "status": "ready",
        "ready": True,
        "app_name": settings.app_name,
        "dependencies": {
            "openf1": {
                "mode": settings.openf1_mode,
                "ready": True,
            }
        },
        "request_id": request_id_context.get(),
    }
