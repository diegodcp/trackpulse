from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from trackpulse_api.dependencies import get_ingest_service
from trackpulse_api.schemas.ingest import IngestStatusResponse, IngestTriggerResponse
from trackpulse_api.services.ingest_service import IngestService

router = APIRouter(prefix="/api/v1/sessions", tags=["ingest"])


@router.post("/{session_key}/ingest", status_code=202, response_model=IngestTriggerResponse)
async def trigger_ingest(
    session_key: int,
    background_tasks: BackgroundTasks,
    service: IngestService = Depends(get_ingest_service),
):
    """Trigger bulk data ingest for a session. Returns immediately."""
    try:
        # Validate session exists
        await service._get_session_id(session_key)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Session {session_key} not found")

    background_tasks.add_task(service.start_ingest, session_key)
    return IngestTriggerResponse(status="accepted", session_key=session_key)


@router.get("/{session_key}/ingest/status", response_model=IngestStatusResponse)
async def get_ingest_status(
    session_key: int,
    service: IngestService = Depends(get_ingest_service),
):
    """Get current ingest progress for a session."""
    try:
        progress = await service.get_progress(session_key)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Session {session_key} not found")
    return IngestStatusResponse(**progress)
