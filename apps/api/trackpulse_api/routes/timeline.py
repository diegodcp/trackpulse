from fastapi import APIRouter, Depends, HTTPException, Path, Query

from trackpulse_api.dependencies import get_timeline_service
from trackpulse_api.schemas.timeline import (
    CarFrameSchema,
    CarTimelineResponse,
    TimelineFrameSchema,
)
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError
from trackpulse_api.services.timeline_service import TimelineService

router = APIRouter(prefix="/api/v1/sessions", tags=["timeline"])


@router.get("/{session_key}/timeline/cars", response_model=CarTimelineResponse)
async def get_car_timeline(
    session_key: int = Path(..., description="OpenF1 session key"),
    hz: float = Query(4.0, ge=1.0, le=10.0, description="Target sample rate"),
    service: TimelineService = Depends(get_timeline_service),
):
    """
    Get pre-computed car position timeline for animation playback.

    Returns a uniform-interval timeline with all drivers' positions
    interpolated to the requested sample rate.
    """
    try:
        timeline = await service.get_or_build_car_timeline(session_key, hz)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InsufficientDataError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return CarTimelineResponse(
        session_key=session_key,
        total_frames=len(timeline),
        duration_seconds=timeline[-1].elapsed_seconds if timeline else 0,
        target_hz=hz,
        frames=[
            TimelineFrameSchema(
                timestamp=f.timestamp,
                elapsed_seconds=f.elapsed_seconds,
                cars=[
                    CarFrameSchema(
                        driver_number=c.driver_number,
                        x=c.x,
                        y=c.y,
                        speed=c.speed,
                        position=c.position,
                        lap_number=c.lap_number,
                        name_acronym=c.name_acronym,
                        team_colour=c.team_colour,
                    )
                    for c in f.cars
                ],
            )
            for f in timeline
        ],
    )
