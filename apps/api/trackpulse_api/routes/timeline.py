from fastapi import APIRouter, Depends, HTTPException, Path, Query

import numpy as np

from trackpulse_api.dependencies import get_timeline_service
from trackpulse_api.processing.downsample import lttb_downsample
from trackpulse_api.schemas.timeline import (
    CarFrameSchema,
    CarTimelineResponse,
    CompactChunkResponse,
    DriverMetaSchema,
    DriverPositionsSchema,
    TimelineFrameSchema,
    TimelineMetaResponse,
)
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError
from trackpulse_api.services.timeline_service import TimelineService

router = APIRouter(prefix="/api/v1/sessions", tags=["timeline"])


@router.get(
    "/{session_key}/timeline/cars/meta",
    response_model=TimelineMetaResponse,
)
async def get_timeline_meta(
    session_key: int = Path(..., description="OpenF1 session key"),
    hz: float = Query(2.0, ge=0.5, le=10.0, description="Target sample rate"),
    chunk_seconds: float = Query(
        120.0, ge=10.0, le=600.0, description="Chunk duration in seconds"
    ),
    service: TimelineService = Depends(get_timeline_service),
):
    """
    Get lightweight timeline metadata without any position data.

    Returns driver list, total duration, chunk count — everything needed
    to render the UI shell before streaming begins. Response < 2KB.
    """
    try:
        meta = await service.get_timeline_meta(session_key, hz, chunk_seconds)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InsufficientDataError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return TimelineMetaResponse(
        session_key=meta["session_key"],
        total_duration_seconds=meta["total_duration_seconds"],
        target_hz=meta["target_hz"],
        total_chunks=meta["total_chunks"],
        chunk_seconds=meta["chunk_seconds"],
        drivers=[
            DriverMetaSchema(
                driver_number=d["driver_number"],
                name_acronym=d["name_acronym"],
                team_colour=d["team_colour"],
            )
            for d in meta["drivers"]
        ],
        race_start_elapsed_seconds=meta.get("race_start_elapsed_seconds"),
    )


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

    Uses direct database range query — only fetches the rows for the
    requested chunk (not the full timeline).
    """
    try:
        # Fast path: query only the chunk's rows directly from DB
        chunk_data = await service.get_compact_chunk(
            session_key=session_key,
            chunk_index=chunk,
            chunk_seconds=chunk_seconds,
            target_hz=hz,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InsufficientDataError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if chunk_data is None:
        # No pre-computed timeline — build and store, then retry
        try:
            await service.get_or_build_car_timeline(session_key, hz)
            chunk_data = await service.get_compact_chunk(
                session_key=session_key,
                chunk_index=chunk,
                chunk_seconds=chunk_seconds,
                target_hz=hz,
            )
        except SessionNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
        except InsufficientDataError as e:
            raise HTTPException(status_code=422, detail=str(e))

    if chunk_data is None:
        raise HTTPException(status_code=422, detail="No timeline data available")

    if chunk >= chunk_data["total_chunks"]:
        raise HTTPException(
            status_code=404,
            detail=f"Chunk {chunk} not found (total: {chunk_data['total_chunks']})",
        )

    return CompactChunkResponse(
        session_key=chunk_data["session_key"],
        total_duration_seconds=chunk_data["total_duration_seconds"],
        target_hz=chunk_data["target_hz"],
        total_chunks=chunk_data["total_chunks"],
        chunk_index=chunk_data["chunk_index"],
        chunk_start_seconds=chunk_data["chunk_start_seconds"],
        chunk_end_seconds=chunk_data["chunk_end_seconds"],
        frame_count=chunk_data["frame_count"],
        drivers=[
            DriverMetaSchema(
                driver_number=d["driver_number"],
                name_acronym=d["name_acronym"],
                team_colour=d["team_colour"],
            )
            for d in chunk_data["drivers"]
        ],
        elapsed=chunk_data["elapsed"],
        positions={
            k: DriverPositionsSchema(**v) for k, v in chunk_data["positions"].items()
        },
        race_start_elapsed_seconds=chunk_data.get("race_start_elapsed_seconds"),
    )


@router.get("/{session_key}/timeline/cars/{driver_number}/speed-trace")
async def get_speed_trace(
    session_key: int = Path(..., description="OpenF1 session key"),
    driver_number: int = Path(..., description="Driver number"),
    points: int = Query(default=1000, ge=100, le=5000, description="Target output points"),
    service: TimelineService = Depends(get_timeline_service),
):
    """
    Get a downsampled speed trace for a single driver.

    Uses the LTTB (Largest Triangle Three Buckets) algorithm to reduce
    potentially 100k+ raw data points to a target number of visual points,
    preserving peaks and valleys. Ideal for charting on screens where pixel
    density is much lower than data density.

    Returns ~1000 points regardless of race length.
    """
    try:
        raw_elapsed, raw_speed = await service.get_driver_speed_series(
            session_key, driver_number
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InsufficientDataError as e:
        raise HTTPException(status_code=422, detail=str(e))

    elapsed_arr = np.array(raw_elapsed, dtype=np.float64)
    speed_arr = np.array(raw_speed, dtype=np.float64)

    ds_elapsed, ds_speed = lttb_downsample(elapsed_arr, speed_arr, points)

    return {
        "session_key": session_key,
        "driver_number": driver_number,
        "total_points": len(raw_elapsed),
        "returned_points": len(ds_elapsed),
        "elapsed": [round(float(v), 3) for v in ds_elapsed],
        "speed": [round(float(v), 1) for v in ds_speed],
    }
