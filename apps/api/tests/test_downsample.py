"""Tests for the LTTB downsampling algorithm and speed-trace endpoint."""

from unittest.mock import AsyncMock

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from trackpulse_api.config import Settings
from trackpulse_api.dependencies import get_timeline_service
from trackpulse_api.main import create_app
from trackpulse_api.processing.downsample import lttb_downsample
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError
from trackpulse_api.services.timeline_service import TimelineService


# --- Pure LTTB algorithm tests ---


def test_lttb_identity_when_below_target():
    """No downsampling when data has fewer points than target."""
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    y = np.array([10.0, 20.0, 15.0, 25.0, 5.0])

    ds_x, ds_y = lttb_downsample(x, y, target_points=10)

    np.testing.assert_array_equal(ds_x, x)
    np.testing.assert_array_equal(ds_y, y)


def test_lttb_identity_when_equal_target():
    """No downsampling when data matches target exactly."""
    x = np.arange(100, dtype=np.float64)
    y = np.sin(x / 10.0)

    ds_x, ds_y = lttb_downsample(x, y, target_points=100)

    np.testing.assert_array_equal(ds_x, x)
    np.testing.assert_array_equal(ds_y, y)


def test_lttb_preserves_first_and_last():
    """First and last points are always retained."""
    x = np.arange(1000, dtype=np.float64)
    y = np.random.default_rng(42).random(1000)

    ds_x, ds_y = lttb_downsample(x, y, target_points=50)

    assert ds_x[0] == x[0]
    assert ds_x[-1] == x[-1]
    assert ds_y[0] == y[0]
    assert ds_y[-1] == y[-1]


def test_lttb_output_size():
    """Output has exactly target_points elements."""
    x = np.arange(10000, dtype=np.float64)
    y = np.sin(x / 100.0) * 300

    ds_x, ds_y = lttb_downsample(x, y, target_points=500)

    assert len(ds_x) == 500
    assert len(ds_y) == 500


def test_lttb_preserves_peaks():
    """LTTB preserves prominent peaks and valleys."""
    # Create signal with a clear spike at index 500
    x = np.arange(1000, dtype=np.float64)
    y = np.zeros(1000)
    y[500] = 100.0  # large spike

    ds_x, ds_y = lttb_downsample(x, y, target_points=100)

    # The spike should be preserved (it has max triangle area)
    assert 100.0 in ds_y


def test_lttb_monotonic_x():
    """Output x values remain monotonically increasing."""
    x = np.linspace(0, 7200, 100000)  # 2-hour race worth of data
    y = np.sin(x / 60) * 50 + 250  # speed oscillating around 250 km/h

    ds_x, ds_y = lttb_downsample(x, y, target_points=1000)

    # Verify monotonicity
    diffs = np.diff(ds_x)
    assert np.all(diffs > 0), "Output x must be strictly increasing"


def test_lttb_target_below_3():
    """Target < 3 returns identity (can't form triangles)."""
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

    ds_x, ds_y = lttb_downsample(x, y, target_points=2)

    np.testing.assert_array_equal(ds_x, x)
    np.testing.assert_array_equal(ds_y, y)


# --- Speed-trace endpoint tests ---


@pytest.fixture
def app():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    return create_app(settings)


@pytest.mark.asyncio
async def test_speed_trace_success(app):
    """GET speed-trace returns downsampled data."""
    # 5000 data points
    elapsed = [float(i) * 0.5 for i in range(5000)]
    speeds = [200.0 + (i % 100) for i in range(5000)]

    mock = AsyncMock(spec=TimelineService)
    mock.get_driver_speed_series.return_value = (elapsed, speeds)
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/sessions/9472/timeline/cars/1/speed-trace?points=500"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_key"] == 9472
    assert data["driver_number"] == 1
    assert data["total_points"] == 5000
    assert data["returned_points"] == 500
    assert len(data["elapsed"]) == 500
    assert len(data["speed"]) == 500
    # First and last preserved
    assert data["elapsed"][0] == 0.0
    assert data["elapsed"][-1] == elapsed[-1]


@pytest.mark.asyncio
async def test_speed_trace_no_downsample_when_small(app):
    """Returns all points when data is smaller than target."""
    elapsed = [0.0, 0.5, 1.0, 1.5, 2.0]
    speeds = [200.0, 220.0, 210.0, 230.0, 215.0]

    mock = AsyncMock(spec=TimelineService)
    mock.get_driver_speed_series.return_value = (elapsed, speeds)
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/sessions/9472/timeline/cars/1/speed-trace?points=1000"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_points"] == 5
    assert data["returned_points"] == 5


@pytest.mark.asyncio
async def test_speed_trace_session_not_found(app):
    """Returns 404 when session doesn't exist."""
    mock = AsyncMock(spec=TimelineService)
    mock.get_driver_speed_series.side_effect = SessionNotFoundError("Not found")
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/sessions/9999/timeline/cars/1/speed-trace"
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_speed_trace_no_data(app):
    """Returns 422 when no speed data for driver."""
    mock = AsyncMock(spec=TimelineService)
    mock.get_driver_speed_series.side_effect = InsufficientDataError("No data")
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/sessions/9472/timeline/cars/99/speed-trace"
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_speed_trace_points_validation(app):
    """Points param is validated (100-5000)."""
    mock = AsyncMock(spec=TimelineService)
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/sessions/9472/timeline/cars/1/speed-trace?points=50"
        )
    assert resp.status_code == 422

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/sessions/9472/timeline/cars/1/speed-trace?points=10000"
        )
    assert resp.status_code == 422
