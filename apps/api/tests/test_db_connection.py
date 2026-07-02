"""Tests for database connectivity and health readiness check."""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_db_select_one(db_session):
    """Database connection works and can execute a simple query."""
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_health_ready_includes_db(async_client):
    """Readiness endpoint reports db status when DB is configured."""
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"]["db"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_status_ok_when_db_healthy(async_client):
    """Status is 'ok' when all dependencies pass."""
    response = await async_client.get("/health/ready")
    body = response.json()
    assert body["status"] == "ok"
