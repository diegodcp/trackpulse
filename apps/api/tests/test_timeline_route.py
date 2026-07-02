"""Tests for the timeline route — endpoint integration tests."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from trackpulse_api.config import Settings
from trackpulse_api.dependencies import get_timeline_service
from trackpulse_api.main import create_app
from trackpulse_api.processing.car_timeline_builder import CarFrame, TimelineFrame
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError
from trackpulse_api.services.timeline_service import TimelineService

T0 = datetime(2024, 3, 2, 15, 0, 0, tzinfo=timezone.utc)


def _make_timeline(num_frames: int = 5, num_drivers: int = 2) -> list[TimelineFrame]:
    """Create a small test timeline."""
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
        frames.append(TimelineFrame(
            timestamp=(T0 + timedelta(seconds=i * 0.25)).isoformat(),
            elapsed_seconds=i * 0.25,
            cars=cars,
        ))
    return frames


def _mock_service(return_value=None, side_effect=None):
    """Create a mock TimelineService with the given behavior."""
    mock = AsyncMock(spec=TimelineService)
    if side_effect:
        mock.get_or_build_car_timeline.side_effect = side_effect
    else:
        mock.get_or_build_car_timeline.return_value = return_value
    return mock


@pytest.fixture
def app():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    return create_app(settings)


@pytest.mark.asyncio
async def test_get_car_timeline_success(app):
    """GET /api/v1/sessions/{key}/timeline/cars returns timeline on success."""
    timeline = _make_timeline(num_frames=5, num_drivers=2)
    mock = _mock_service(return_value=timeline)
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/sessions/9472/timeline/cars?hz=4")

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_key"] == 9472
    assert data["total_frames"] == 5
    assert data["target_hz"] == 4.0
    assert len(data["frames"]) == 5
    assert len(data["frames"][0]["cars"]) == 2
    # Verify car schema
    car = data["frames"][0]["cars"][0]
    assert "driver_number" in car
    assert "x" in car
    assert "y" in car
    assert "name_acronym" in car
    assert "team_colour" in car


@pytest.mark.asyncio
async def test_get_car_timeline_session_not_found(app):
    """Returns 404 when session not found."""
    mock = _mock_service(side_effect=SessionNotFoundError("Not found"))
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/sessions/9999/timeline/cars")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_car_timeline_insufficient_data(app):
    """Returns 422 when no position data available."""
    mock = _mock_service(side_effect=InsufficientDataError("No car position data"))
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/sessions/9472/timeline/cars")

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_car_timeline_hz_validation(app):
    """hz query param is validated (1.0-10.0)."""
    mock = _mock_service(return_value=[])
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/sessions/9472/timeline/cars?hz=0.5")
    assert resp.status_code == 422

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/sessions/9472/timeline/cars?hz=15")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_car_timeline_default_hz(app):
    """Default hz is 4.0."""
    timeline = _make_timeline(num_frames=3, num_drivers=1)
    mock = _mock_service(return_value=timeline)
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/sessions/9472/timeline/cars")

    assert resp.status_code == 200
    mock.get_or_build_car_timeline.assert_called_once_with(9472, 4.0)
