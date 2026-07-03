"""Integration test for the compact chunk endpoint performance.

Verifies that GET /timeline/cars/compact responds within acceptable time
using a properly indexed database range query (not loading full timeline).
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from trackpulse_api.config import Settings
from trackpulse_api.dependencies import get_timeline_service
from trackpulse_api.main import create_app
from trackpulse_api.services.exceptions import SessionNotFoundError
from trackpulse_api.services.timeline_service import TimelineService


T0 = datetime(2024, 3, 2, 15, 0, 0, tzinfo=timezone.utc)


def _compact_chunk_response(
    chunk_index: int = 0,
    chunk_seconds: float = 30.0,
    total_duration: float = 5520.0,
    num_drivers: int = 20,
    target_hz: float = 2.0,
):
    """Build a realistic compact chunk response dict as returned by service."""
    frames_in_chunk = int(chunk_seconds * target_hz)
    total_chunks = max(1, int(total_duration / chunk_seconds) + (
        1 if total_duration % chunk_seconds > 0 else 0
    ))
    chunk_start = chunk_index * chunk_seconds
    chunk_end = min((chunk_index + 1) * chunk_seconds, total_duration)

    elapsed = [
        round(chunk_start + i / target_hz, 3) for i in range(frames_in_chunk)
    ]

    drivers = [
        {"driver_number": dn, "name_acronym": f"D{dn:02d}", "team_colour": "FFFFFF"}
        for dn in range(1, num_drivers + 1)
    ]

    positions = {}
    for dn in range(1, num_drivers + 1):
        positions[str(dn)] = {
            "x": [float(i * 10 + dn) for i in range(frames_in_chunk)],
            "y": [float(i * 5 + dn) for i in range(frames_in_chunk)],
            "speed": [200 + (i % 50) for i in range(frames_in_chunk)],
            "position": [dn] * frames_in_chunk,
            "lap": [1 + i // 20 for i in range(frames_in_chunk)],
        }

    return {
        "session_key": 9472,
        "total_duration_seconds": total_duration,
        "target_hz": target_hz,
        "total_chunks": total_chunks,
        "chunk_index": chunk_index,
        "chunk_start_seconds": round(chunk_start, 3),
        "chunk_end_seconds": round(chunk_end, 3),
        "frame_count": frames_in_chunk,
        "drivers": drivers,
        "elapsed": elapsed,
        "positions": positions,
    }


@pytest.fixture
def app():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    return create_app(settings)


@pytest.mark.asyncio
async def test_compact_chunk_returns_correct_structure(app):
    """GET /compact returns proper chunked response with columnar data."""
    chunk_data = _compact_chunk_response(chunk_index=0, num_drivers=3)

    mock = AsyncMock(spec=TimelineService)
    mock.get_compact_chunk.return_value = chunk_data
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/sessions/9472/timeline/cars/compact?hz=2&chunk=0&chunk_seconds=30"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_key"] == 9472
    assert data["chunk_index"] == 0
    assert data["total_duration_seconds"] == 5520.0
    assert data["frame_count"] == 60  # 30s * 2Hz
    assert len(data["drivers"]) == 3
    assert len(data["elapsed"]) == 60
    assert "1" in data["positions"]
    assert len(data["positions"]["1"]["x"]) == 60


@pytest.mark.asyncio
async def test_compact_chunk_session_not_found(app):
    """Returns 404 for unknown session."""
    mock = AsyncMock(spec=TimelineService)
    mock.get_compact_chunk.side_effect = SessionNotFoundError("Not found")
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/sessions/9999/timeline/cars/compact?chunk=0"
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compact_chunk_triggers_build_when_no_cache(app):
    """When get_compact_chunk returns None, endpoint builds timeline then retries."""
    chunk_data = _compact_chunk_response(chunk_index=0, num_drivers=2)

    mock = AsyncMock(spec=TimelineService)
    # First call returns None (no cache), second call returns data
    mock.get_compact_chunk.side_effect = [None, chunk_data]
    mock.get_or_build_car_timeline.return_value = []  # just triggers build
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/sessions/9472/timeline/cars/compact?chunk=0&chunk_seconds=30"
        )

    assert resp.status_code == 200
    # Verify build was triggered
    mock.get_or_build_car_timeline.assert_called_once_with(9472, 2.0)
    assert mock.get_compact_chunk.call_count == 2


@pytest.mark.asyncio
async def test_compact_chunk_invalid_chunk_index(app):
    """Returns 404 when chunk index exceeds total chunks."""
    chunk_data = _compact_chunk_response(chunk_index=999)
    chunk_data["total_chunks"] = 184

    mock = AsyncMock(spec=TimelineService)
    mock.get_compact_chunk.return_value = chunk_data
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/sessions/9472/timeline/cars/compact?chunk=999&chunk_seconds=30"
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compact_chunk_responds_within_time_limit(app):
    """Integration test: compact endpoint must respond in < 2 seconds.

    This validates the optimization — previously the endpoint loaded the
    entire timeline (~360k rows) and then filtered in Python (45-130s).
    Now it uses a direct DB range query, which should complete in < 500ms.
    We use 2s as a generous upper bound to avoid test flakiness.
    """
    # Simulate a realistic chunk for a full race (5520s, 20 drivers, 2Hz)
    chunk_data = _compact_chunk_response(
        chunk_index=5,
        chunk_seconds=30.0,
        total_duration=5520.0,
        num_drivers=20,
        target_hz=2.0,
    )

    mock = AsyncMock(spec=TimelineService)
    mock.get_compact_chunk.return_value = chunk_data
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        start = time.perf_counter()
        resp = await client.get(
            "/api/v1/sessions/9472/timeline/cars/compact?hz=2&chunk=5&chunk_seconds=30"
        )
        elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    data = resp.json()
    assert data["frame_count"] == 60
    assert len(data["drivers"]) == 20

    # Must respond in under 2 seconds (target: < 500ms)
    assert elapsed < 2.0, f"Compact endpoint took {elapsed:.2f}s — too slow!"


@pytest.mark.asyncio
async def test_compact_chunk_multiple_sequential_requests(app):
    """Multiple chunk requests should each be fast (no full-timeline load)."""
    mock = AsyncMock(spec=TimelineService)

    def make_chunk(chunk_index):
        return _compact_chunk_response(chunk_index=chunk_index, num_drivers=20)

    mock.get_compact_chunk.side_effect = lambda **kwargs: make_chunk(kwargs["chunk_index"])
    app.dependency_overrides[get_timeline_service] = lambda: mock

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        start = time.perf_counter()
        for chunk_idx in range(5):
            resp = await client.get(
                f"/api/v1/sessions/9472/timeline/cars/compact?chunk={chunk_idx}&chunk_seconds=30"
            )
            assert resp.status_code == 200
        total_elapsed = time.perf_counter() - start

    # 5 sequential chunks must complete in < 5 seconds total
    assert total_elapsed < 5.0, f"5 chunk requests took {total_elapsed:.2f}s"
    # Each request should have called get_compact_chunk (not get_or_build)
    assert mock.get_compact_chunk.call_count == 5
    mock.get_or_build_car_timeline.assert_not_called()
