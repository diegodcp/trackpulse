import pytest
from unittest.mock import AsyncMock, patch

from trackpulse_api.clients.openf1 import OpenF1UnavailableError
from trackpulse_api.config import Settings
from trackpulse_api.main import create_app
from trackpulse_api.processing.circuit_builder import (
    CircuitGeometry,
    CircuitPoint,
    CircuitSegment,
)
from trackpulse_api.services.exceptions import InsufficientDataError, SessionNotFoundError


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _make_sample_geometry(num_points: int = 100, num_segments: int = 24) -> CircuitGeometry:
    """Build a realistic sample CircuitGeometry for testing."""
    points = [
        CircuitPoint(x=float(i), y=float(i * 0.5), cumulative_dist=float(i * 1.3))
        for i in range(num_points)
    ]
    segments = [
        CircuitSegment(
            id=i,
            start_idx=i * (num_points // num_segments),
            end_idx=(i + 1) * (num_points // num_segments),
            sector=(i % 3) + 1,
            start_dist=float(i * 200),
            end_dist=float((i + 1) * 200),
        )
        for i in range(num_segments)
    ]
    return CircuitGeometry(
        points=points,
        segments=segments,
        bounds={"min_x": 0.0, "max_x": 99.0, "min_y": 0.0, "max_y": 49.5},
        total_length=5303.0,
        source_driver=1,
        source_lap=3,
    )


SAMPLE_GEOMETRY = _make_sample_geometry()


@pytest.fixture
def settings():
    return Settings(database_url=TEST_DATABASE_URL)


@pytest.fixture
def mock_circuit_service():
    return AsyncMock()


@pytest.fixture
def app(settings, mock_circuit_service):
    application = create_app(settings)

    # Override the circuit service dependency
    from trackpulse_api.dependencies import get_circuit_service

    application.dependency_overrides[get_circuit_service] = lambda: mock_circuit_service
    return application


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


class TestGetCircuitGeometry:
    def test_returns_cached_geometry(self, client, mock_circuit_service):
        """Returns 200 with circuit data when geometry exists."""
        mock_circuit_service.get_or_build_circuit.return_value = SAMPLE_GEOMETRY
        response = client.get("/api/v1/sessions/9472/circuit")
        assert response.status_code == 200
        data = response.json()
        assert data["session_key"] == 9472
        assert data["total_points"] == 100
        assert len(data["points"]) == 100
        assert len(data["segments"]) == 24
        assert "bounds" in data
        assert data["total_length"] > 0

    def test_returns_404_for_unknown_session(self, client, mock_circuit_service):
        """Returns 404 when session doesn't exist in OpenF1."""
        mock_circuit_service.get_or_build_circuit.side_effect = SessionNotFoundError()
        response = client.get("/api/v1/sessions/99999/circuit")
        assert response.status_code == 404

    def test_returns_503_when_openf1_down(self, client, mock_circuit_service):
        """Returns 503 when OpenF1 is unreachable."""
        mock_circuit_service.get_or_build_circuit.side_effect = OpenF1UnavailableError()
        response = client.get("/api/v1/sessions/9472/circuit")
        assert response.status_code == 503

    def test_returns_422_for_insufficient_data(self, client, mock_circuit_service):
        """Returns 422 when not enough location data for extraction."""
        mock_circuit_service.get_or_build_circuit.side_effect = InsufficientDataError(
            "fewer than 50 points"
        )
        response = client.get("/api/v1/sessions/9472/circuit")
        assert response.status_code == 422

    def test_response_schema_valid(self, client, mock_circuit_service):
        """Response matches CircuitGeometryResponse schema."""
        mock_circuit_service.get_or_build_circuit.return_value = SAMPLE_GEOMETRY
        response = client.get("/api/v1/sessions/9472/circuit")
        data = response.json()
        assert all(
            key in data for key in ["points", "segments", "bounds", "total_length"]
        )
        assert all(
            key in data["bounds"] for key in ["min_x", "max_x", "min_y", "max_y"]
        )
        assert all(
            key in data["points"][0] for key in ["x", "y", "cumulative_dist"]
        )
        assert all(
            key in data["segments"][0]
            for key in ["id", "start_idx", "end_idx", "sector"]
        )

    def test_session_key_must_be_integer(self, client):
        """Non-integer session_key returns 422."""
        response = client.get("/api/v1/sessions/abc/circuit")
        assert response.status_code == 422

    def test_source_driver_and_lap_included(self, client, mock_circuit_service):
        """Response includes source_driver and source_lap."""
        mock_circuit_service.get_or_build_circuit.return_value = SAMPLE_GEOMETRY
        response = client.get("/api/v1/sessions/9472/circuit")
        data = response.json()
        assert data["source_driver"] == 1
        assert data["source_lap"] == 3
