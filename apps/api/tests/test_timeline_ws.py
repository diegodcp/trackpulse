"""Tests for the WebSocket timeline streaming endpoint."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from trackpulse_api.config import Settings
from trackpulse_api.dependencies import get_timeline_service
from trackpulse_api.main import create_app
from trackpulse_api.processing.car_timeline_builder import CarFrame, TimelineFrame
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError
from trackpulse_api.services.timeline_service import TimelineService

T0 = datetime(2024, 3, 2, 15, 0, 0, tzinfo=timezone.utc)


def _make_timeline(num_frames: int = 20, num_drivers: int = 2, hz: float = 4.0):
    """Create a test timeline with multiple frames."""
    step = 1.0 / hz
    frames = []
    for i in range(num_frames):
        cars = [
            CarFrame(
                driver_number=dn,
                x=float(i * 10 + dn),
                y=float(i * 5 + dn),
                speed=200 + i,
                position=dn,
                lap_number=1,
                name_acronym=f"D{dn:02d}",
                team_colour="FFFFFF",
            )
            for dn in range(1, num_drivers + 1)
        ]
        frames.append(
            TimelineFrame(
                timestamp=(T0 + timedelta(seconds=i * step)).isoformat(),
                elapsed_seconds=round(i * step, 3),
                cars=cars,
            )
        )
    return frames


@pytest.fixture
def app():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    return create_app(settings)


def _override_service(app, timeline=None, side_effect=None):
    """Override get_timeline_service dependency with a mock."""
    mock = AsyncMock(spec=TimelineService)
    if side_effect:
        mock.get_or_build_car_timeline.side_effect = side_effect
    else:
        mock.get_or_build_car_timeline.return_value = timeline
    app.dependency_overrides[get_timeline_service] = lambda: mock
    return mock


def test_websocket_streams_frames(app):
    """Verify WS sends frames at requested Hz."""
    timeline = _make_timeline(num_frames=10, num_drivers=2, hz=4.0)
    _override_service(app, timeline=timeline)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/sessions/9472/timeline/cars/stream?hz=4&speed=1000"
        ) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "frame"
            assert "elapsed" in msg
            assert "cars" in msg
            assert msg["elapsed"] == 0.0

            # Verify car data format (short keys)
            cars = msg["cars"]
            assert "1" in cars
            assert "x" in cars["1"]
            assert "y" in cars["1"]
            assert "s" in cars["1"]
            assert "p" in cars["1"]
            assert "l" in cars["1"]

            # Receive a few more frames
            msg2 = ws.receive_json()
            assert msg2["type"] == "frame"
            assert msg2["elapsed"] > msg["elapsed"]


def test_websocket_seek_command(app):
    """Verify seek resets stream position."""
    timeline = _make_timeline(num_frames=40, num_drivers=1, hz=4.0)
    _override_service(app, timeline=timeline)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/sessions/9472/timeline/cars/stream?hz=4&speed=1000"
        ) as ws:
            # Receive first frame
            msg = ws.receive_json()
            assert msg["type"] == "frame"

            # Send seek command to jump to elapsed=5.0
            ws.send_json({"cmd": "seek", "to": 5.0})

            # Next frames should be at or near elapsed=5.0
            found_seek = False
            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "frame" and msg["elapsed"] >= 4.9:
                    found_seek = True
                    break
            assert found_seek, "Did not receive frame near seek target"


def test_websocket_speed_change(app):
    """Verify speed multiplier is accepted."""
    timeline = _make_timeline(num_frames=20, num_drivers=1, hz=4.0)
    _override_service(app, timeline=timeline)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/sessions/9472/timeline/cars/stream?hz=4&speed=1000"
        ) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "frame"

            # Send speed change
            ws.send_json({"cmd": "speed", "value": 50.0})

            # Should continue streaming
            msg2 = ws.receive_json()
            assert msg2["type"] == "frame"


def test_websocket_pause_resume(app):
    """Verify pause stops frame emission and resume continues."""
    timeline = _make_timeline(num_frames=40, num_drivers=1, hz=4.0)
    _override_service(app, timeline=timeline)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/sessions/9472/timeline/cars/stream?hz=4&speed=1000"
        ) as ws:
            # Get first frame
            msg = ws.receive_json()
            assert msg["type"] == "frame"

            # Pause then immediately resume
            ws.send_json({"cmd": "pause"})
            ws.send_json({"cmd": "resume"})

            # Should get more frames after resume
            msg2 = ws.receive_json()
            assert msg2["type"] == "frame"


def test_websocket_end_message(app):
    """Verify server sends 'end' when timeline is exhausted."""
    # Very short timeline - 3 frames at 4Hz = 0.5s total
    timeline = _make_timeline(num_frames=3, num_drivers=1, hz=4.0)
    _override_service(app, timeline=timeline)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/sessions/9472/timeline/cars/stream?hz=4&speed=1000"
        ) as ws:
            # Drain all frames until end
            messages = []
            for _ in range(20):  # safety limit
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] == "end":
                    break

            assert messages[-1]["type"] == "end"
            frame_msgs = [m for m in messages if m["type"] == "frame"]
            assert len(frame_msgs) >= 2


def test_websocket_session_not_found(app):
    """Verify error + close when session doesn't exist."""
    _override_service(app, side_effect=SessionNotFoundError("Not found"))

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/sessions/9999/timeline/cars/stream"
        ) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["detail"].lower()


def test_websocket_interpolates_between_frames(app):
    """Verify positions are interpolated between timeline frames."""
    # 2 frames: elapsed 0.0 and 1.0
    frames = [
        TimelineFrame(
            timestamp=T0.isoformat(),
            elapsed_seconds=0.0,
            cars=[
                CarFrame(
                    driver_number=1, x=0.0, y=0.0,
                    speed=200, position=1, lap_number=1,
                    name_acronym="VER", team_colour="3671C6",
                )
            ],
        ),
        TimelineFrame(
            timestamp=(T0 + timedelta(seconds=1)).isoformat(),
            elapsed_seconds=1.0,
            cars=[
                CarFrame(
                    driver_number=1, x=100.0, y=50.0,
                    speed=250, position=1, lap_number=1,
                    name_acronym="VER", team_colour="3671C6",
                )
            ],
        ),
    ]
    _override_service(app, timeline=frames)

    with TestClient(app) as client:
        # Start at 0.5 elapsed — should interpolate to x=50, y=25
        with client.websocket_connect(
            "/api/v1/sessions/9472/timeline/cars/stream?hz=2&speed=1000&start_elapsed=0.5"
        ) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "frame"
            assert msg["elapsed"] == 0.5
            car = msg["cars"]["1"]
            assert car["x"] == 50.0
            assert car["y"] == 25.0
