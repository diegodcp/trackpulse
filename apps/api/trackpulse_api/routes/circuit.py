from fastapi import APIRouter, Depends, HTTPException, Path

from trackpulse_api.clients.openf1 import OpenF1UnavailableError
from trackpulse_api.dependencies import get_circuit_service
from trackpulse_api.schemas.circuit import (
    BoundsSchema,
    CircuitGeometryResponse,
    PointSchema,
    SegmentSchema,
)
from trackpulse_api.services.circuit_service import CircuitService
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError

router = APIRouter(prefix="/api/v1/sessions", tags=["circuit"])


@router.get("/{session_key}/circuit", response_model=CircuitGeometryResponse)
async def get_circuit_geometry(
    session_key: int = Path(..., description="OpenF1 session key"),
    circuit_service: CircuitService = Depends(get_circuit_service),
):
    """
    Get circuit centerline geometry for a session.

    Returns pre-computed geometry from cache, or extracts it from
    OpenF1 location data on first request.
    """
    try:
        geometry = await circuit_service.get_or_build_circuit(session_key)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found in OpenF1")
    except OpenF1UnavailableError:
        raise HTTPException(status_code=503, detail={"code": "openf1_unavailable"})
    except InsufficientDataError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return CircuitGeometryResponse(
        session_key=session_key,
        total_points=len(geometry.points),
        total_length=geometry.total_length,
        bounds=BoundsSchema(**geometry.bounds),
        points=[
            PointSchema(x=p.x, y=p.y, cumulative_dist=p.cumulative_dist)
            for p in geometry.points
        ],
        segments=[
            SegmentSchema(
                id=s.id,
                start_idx=s.start_idx,
                end_idx=s.end_idx,
                sector=s.sector,
                start_dist=s.start_dist,
                end_dist=s.end_dist,
            )
            for s in geometry.segments
        ],
        source_driver=geometry.source_driver,
        source_lap=geometry.source_lap,
    )
