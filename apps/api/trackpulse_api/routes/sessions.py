from fastapi import APIRouter, Depends, HTTPException, Query

from trackpulse_api.clients.openf1 import OpenF1UnavailableError
from trackpulse_api.dependencies import get_session_discovery_service
from trackpulse_api.schemas.sessions import MeetingWithSessions

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.get("/sessions", response_model=list[MeetingWithSessions])
async def list_sessions(
    year: int = Query(..., ge=2023, le=2030, description="Season year"),
    country: str | None = Query(None, description="Country name filter"),
    service=Depends(get_session_discovery_service),
):
    try:
        return await service.get_sessions_by_year(year, country)
    except OpenF1UnavailableError:
        raise HTTPException(
            status_code=503, detail={"code": "openf1_unavailable"}
        )
