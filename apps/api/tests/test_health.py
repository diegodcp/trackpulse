import pytest
from httpx import ASGITransport, AsyncClient
from pathlib import Path

from trackpulse_api.main import create_app
from trackpulse_api.settings import AppSettings


@pytest.mark.asyncio
async def test_health_live_returns_200() -> None:
    app = create_app(AppSettings())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_returns_200_in_fixture_mode() -> None:
    app = create_app(AppSettings(openf1_mode="fixture"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")

    payload = response.json()
    assert response.status_code == 200
    assert payload["ready"] is True
    assert payload["dependencies"]["openf1"]["mode"] == "fixture"


@pytest.mark.asyncio
async def test_health_ready_includes_db_dependency_when_enabled(tmp_path: Path) -> None:
    db_url = f"sqlite+aiosqlite:///{(tmp_path / 'ready-check.db').as_posix()}"
    app = create_app(AppSettings(openf1_mode="fixture", db_enabled=True, db_url=db_url))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")

    payload = response.json()
    assert response.status_code == 200
    assert payload["ready"] is True
    assert payload["dependencies"]["db"]["enabled"] is True
    assert payload["dependencies"]["db"]["ready"] is True


@pytest.mark.asyncio
async def test_version_includes_app_name() -> None:
    app = create_app(AppSettings(app_name="TrackPulse API"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/version")

    payload = response.json()
    assert response.status_code == 200
    assert "TrackPulse" in payload["service"]
    assert payload["app_name"] == "TrackPulse API"
