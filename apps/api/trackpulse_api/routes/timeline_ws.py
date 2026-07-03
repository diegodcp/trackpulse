"""WebSocket streaming endpoint for car timeline playback.

Streams car positions as tiny JSON ticks at the requested Hz,
allowing the frontend to render smoothly without loading bulk data.
"""

import asyncio
import bisect
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from trackpulse_api.dependencies import get_timeline_service
from trackpulse_api.processing.car_timeline_builder import TimelineFrame
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError
from trackpulse_api.services.timeline_service import TimelineService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["timeline-ws"])


def _extract_frame_at(
    timeline: list[TimelineFrame],
    elapsed_index: list[float],
    elapsed: float,
) -> dict[str, dict]:
    """Extract car positions at a given elapsed time via binary search + interpolation.

    Returns compact dict: {driver_number_str: {"x", "y", "s", "p", "l"}}
    """
    if not timeline:
        return {}

    # Binary search for the surrounding frames
    idx = bisect.bisect_right(elapsed_index, elapsed)

    if idx == 0:
        frame = timeline[0]
    elif idx >= len(timeline):
        frame = timeline[-1]
    else:
        # Linear interpolation between frames
        before = timeline[idx - 1]
        after = timeline[idx]
        t_range = after.elapsed_seconds - before.elapsed_seconds
        if t_range <= 0:
            frame = before
        else:
            t = (elapsed - before.elapsed_seconds) / t_range
            return _interpolate_frames(before, after, t)

    return _frame_to_compact(frame)


def _frame_to_compact(frame: TimelineFrame) -> dict[str, dict]:
    """Convert a TimelineFrame to compact wire format."""
    result = {}
    for car in frame.cars:
        result[str(car.driver_number)] = {
            "x": round(car.x, 1),
            "y": round(car.y, 1),
            "s": car.speed,
            "p": car.position,
            "l": car.lap_number,
        }
    return result


def _interpolate_frames(
    before: TimelineFrame, after: TimelineFrame, t: float
) -> dict[str, dict]:
    """Linearly interpolate between two frames."""
    before_cars = {c.driver_number: c for c in before.cars}
    after_cars = {c.driver_number: c for c in after.cars}
    all_drivers = set(before_cars.keys()) | set(after_cars.keys())

    result = {}
    for dn in all_drivers:
        b = before_cars.get(dn)
        a = after_cars.get(dn)
        if b and a:
            x = round(b.x + (a.x - b.x) * t, 1)
            y = round(b.y + (a.y - b.y) * t, 1)
            # Forward-fill discrete values from 'before'
            result[str(dn)] = {
                "x": x,
                "y": y,
                "s": b.speed,
                "p": b.position,
                "l": b.lap_number,
            }
        elif b:
            result[str(dn)] = {
                "x": round(b.x, 1),
                "y": round(b.y, 1),
                "s": b.speed,
                "p": b.position,
                "l": b.lap_number,
            }
        elif a:
            result[str(dn)] = {
                "x": round(a.x, 1),
                "y": round(a.y, 1),
                "s": a.speed,
                "p": a.position,
                "l": a.lap_number,
            }
    return result


def _handle_command(
    msg: dict, current_elapsed: float, speed: float, paused: bool, total_duration: float
) -> tuple[float, float, bool]:
    """Process a client command message. Returns (elapsed, speed, paused)."""
    cmd = msg.get("cmd")
    if cmd == "seek":
        target = float(msg.get("to", 0))
        current_elapsed = max(0.0, min(target, total_duration))
    elif cmd == "speed":
        value = float(msg.get("value", 1.0))
        speed = max(0.1, min(value, 100.0))
    elif cmd == "pause":
        paused = True
    elif cmd == "resume":
        paused = False
    return current_elapsed, speed, paused


@router.websocket("/api/v1/sessions/{session_key}/timeline/cars/stream")
async def stream_car_timeline(
    websocket: WebSocket,
    session_key: int,
    service: TimelineService = Depends(get_timeline_service),
):
    """
    Stream car positions as tiny JSON ticks at the requested Hz.

    Query params (parsed manually for WebSocket compatibility):
    - hz: Target sample rate (default 4.0)
    - start_elapsed: Starting position in seconds (default 0.0)
    - speed: Playback speed multiplier (default 1.0)

    Protocol:
    - Server sends frames at (hz * speed) ticks per wall-clock second
    - Client can send JSON commands:
        {"cmd": "seek", "to": 120.5}
        {"cmd": "speed", "value": 5.0}
        {"cmd": "pause"}
        {"cmd": "resume"}
    - Server sends {"type": "frame", "elapsed": 45.25, "cars": {...}}
    - Server sends {"type": "end"} when race finishes
    """
    # Parse query params manually (FastAPI Query validators don't work on WebSocket)
    params = websocket.query_params
    hz = max(0.5, min(float(params.get("hz", "4.0")), 10.0))
    start_elapsed = max(0.0, float(params.get("start_elapsed", "0.0")))
    speed = max(0.1, min(float(params.get("speed", "1.0")), 100.0))

    await websocket.accept()

    try:
        timeline = await service.get_or_build_car_timeline(session_key, hz)
    except (SessionNotFoundError, InsufficientDataError) as e:
        await websocket.send_json({"type": "error", "detail": str(e)})
        await websocket.close(code=1008)
        return
    except Exception as e:
        logger.exception("Unexpected error loading timeline for session %d", session_key)
        await websocket.send_json({"type": "error", "detail": f"Internal error: {e}"})
        await websocket.close(code=1011)
        return

    if not timeline:
        await websocket.send_json({"type": "error", "detail": "No timeline data"})
        await websocket.close(code=1008)
        return

    total_duration = timeline[-1].elapsed_seconds
    # Pre-build elapsed index for fast binary search
    elapsed_index = [f.elapsed_seconds for f in timeline]

    # Clamp start_elapsed
    current_elapsed = max(0.0, min(start_elapsed, total_duration))
    paused = False
    step = 1.0 / hz

    # Use a queue to decouple receiving commands from the send loop.
    # This avoids cancelling websocket.receive_json() which can close the connection.
    cmd_queue: asyncio.Queue[dict] = asyncio.Queue()

    async def _receive_commands():
        try:
            while True:
                msg = await websocket.receive_json()
                await cmd_queue.put(msg)
        except WebSocketDisconnect:
            await cmd_queue.put({"cmd": "_disconnect"})

    receiver_task = asyncio.create_task(_receive_commands())

    try:
        while current_elapsed <= total_duration:
            # Drain all pending commands (non-blocking)
            while not cmd_queue.empty():
                msg = cmd_queue.get_nowait()
                if msg.get("cmd") == "_disconnect":
                    return
                current_elapsed, speed, paused = _handle_command(
                    msg, current_elapsed, speed, paused, total_duration
                )

            if paused:
                await asyncio.sleep(0.05)
                continue

            # Extract and send current frame
            cars = _extract_frame_at(timeline, elapsed_index, current_elapsed)
            await websocket.send_json({
                "type": "frame",
                "elapsed": round(current_elapsed, 3),
                "cars": cars,
            })

            # Advance by 1/hz seconds of race time
            current_elapsed += step

            # Wait real-time interval (adjusted for speed)
            await asyncio.sleep(step / speed)

        await websocket.send_json({"type": "end"})
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for session %d", session_key)
    finally:
        receiver_task.cancel()
        try:
            await receiver_task
        except asyncio.CancelledError:
            pass
