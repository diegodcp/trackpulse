from fastapi import APIRouter, Depends, HTTPException, Path, Query

from trackpulse_api.dependencies import get_timeline_service
from trackpulse_api.schemas.timeline import (
    CarFrameSchema,
    CarTimelineResponse,
    CompactChunkResponse,
    DriverMetaSchema,
    DriverPositionsSchema,
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


@router.get(
    "/{session_key}/timeline/cars/compact",
    response_model=CompactChunkResponse,
)
async def get_car_timeline_compact(
    session_key: int = Path(..., description="OpenF1 session key"),
    hz: float = Query(2.0, ge=0.5, le=10.0, description="Target sample rate"),
    chunk: int = Query(0, ge=0, description="Chunk index (0-based)"),
    chunk_seconds: float = Query(
        120.0, ge=10.0, le=600.0, description="Chunk duration in seconds"
    ),
    service: TimelineService = Depends(get_timeline_service),
):
    """
    Get car timeline in compact chunked format for efficient streaming.

    Returns one time-window chunk with driver metadata sent once and
    positions as flat arrays (columnar). Much smaller payload than the
    full frames endpoint.
    """
    try:
        timeline = await service.get_or_build_car_timeline(session_key, hz)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InsufficientDataError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not timeline:
        raise HTTPException(status_code=422, detail="No timeline data available")

    total_duration = timeline[-1].elapsed_seconds
    total_chunks = max(1, int(total_duration / chunk_seconds) + (
        1 if total_duration % chunk_seconds > 0 else 0
    ))

    if chunk >= total_chunks:
        raise HTTPException(
            status_code=404,
            detail=f"Chunk {chunk} not found (total: {total_chunks})",
        )

    chunk_start = chunk * chunk_seconds
    chunk_end = min((chunk + 1) * chunk_seconds, total_duration)

    # Filter frames within this chunk's time window
    chunk_frames = [
        f for f in timeline
        if chunk_start <= f.elapsed_seconds < chunk_end
        or (chunk == total_chunks - 1 and f.elapsed_seconds == total_duration)
    ]

    if not chunk_frames:
        chunk_frames = []

    # Collect all drivers present in this chunk
    driver_numbers_seen: set[int] = set()
    driver_meta_map: dict[int, dict] = {}
    for f in chunk_frames:
        for c in f.cars:
            if c.driver_number not in driver_meta_map:
                driver_meta_map[c.driver_number] = {
                    "name_acronym": c.name_acronym,
                    "team_colour": c.team_colour,
                }
            driver_numbers_seen.add(c.driver_number)

    driver_numbers = sorted(driver_numbers_seen)
    drivers = [
        DriverMetaSchema(
            driver_number=dn,
            name_acronym=driver_meta_map[dn]["name_acronym"],
            team_colour=driver_meta_map[dn]["team_colour"],
        )
        for dn in driver_numbers
    ]

    # Build elapsed array and per-driver position arrays
    elapsed: list[float] = []
    positions: dict[str, dict[str, list]] = {
        str(dn): {"x": [], "y": [], "speed": [], "position": [], "lap": []}
        for dn in driver_numbers
    }

    for f in chunk_frames:
        elapsed.append(round(f.elapsed_seconds, 3))
        cars_in_frame = {c.driver_number: c for c in f.cars}

        for dn in driver_numbers:
            car = cars_in_frame.get(dn)
            if car:
                positions[str(dn)]["x"].append(round(car.x, 1))
                positions[str(dn)]["y"].append(round(car.y, 1))
                positions[str(dn)]["speed"].append(car.speed)
                positions[str(dn)]["position"].append(car.position)
                positions[str(dn)]["lap"].append(car.lap_number)
            else:
                positions[str(dn)]["x"].append(None)
                positions[str(dn)]["y"].append(None)
                positions[str(dn)]["speed"].append(None)
                positions[str(dn)]["position"].append(None)
                positions[str(dn)]["lap"].append(None)

    return CompactChunkResponse(
        session_key=session_key,
        total_duration_seconds=round(total_duration, 3),
        target_hz=hz,
        total_chunks=total_chunks,
        chunk_index=chunk,
        chunk_start_seconds=round(chunk_start, 3),
        chunk_end_seconds=round(chunk_end, 3),
        frame_count=len(chunk_frames),
        drivers=drivers,
        elapsed=elapsed,
        positions={
            k: DriverPositionsSchema(**v) for k, v in positions.items()
        },
    )
