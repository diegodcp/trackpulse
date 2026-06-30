from fastapi import APIRouter, Depends

from ..settings import AppSettings, get_settings

router = APIRouter(tags=["version"])


@router.get("/version")
def version(settings: AppSettings = Depends(get_settings)) -> dict[str, object]:
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "service": f"{settings.app_name} {settings.app_version}",
        "openf1_mode": settings.openf1_mode,
    }
