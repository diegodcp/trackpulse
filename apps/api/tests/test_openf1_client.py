import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from trackpulse_api.clients.openf1 import OpenF1Client, OpenF1UnavailableError


@pytest.fixture
def mock_async_client():
    """Create a mock httpx.AsyncClient that works as an async context manager."""
    mock_client_instance = AsyncMock()
    mock_client_class = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)
    return mock_client_class, mock_client_instance


@pytest.mark.asyncio
async def test_get_meetings_success(mock_async_client):
    """Client correctly fetches and returns meetings list."""
    mock_class, mock_instance = mock_async_client
    mock_instance.get = AsyncMock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "meeting_key": 1219,
                    "meeting_name": "Bahrain Grand Prix",
                    "country_name": "Bahrain",
                    "location": "Sakhir",
                    "circuit_short_name": "Bahrain",
                    "year": 2023,
                    "date_start": "2023-03-03T00:00:00+00:00",
                }
            ],
        )
    )
    with patch("httpx.AsyncClient", mock_class):
        client = OpenF1Client(base_url="https://api.openf1.org/v1")
        result = await client.get_meetings(year=2023)
        assert len(result) == 1
        assert result[0]["meeting_key"] == 1219


@pytest.mark.asyncio
async def test_get_meetings_with_country_filter(mock_async_client):
    """Client passes country parameter correctly."""
    mock_class, mock_instance = mock_async_client
    mock_instance.get = AsyncMock(return_value=httpx.Response(200, json=[]))
    with patch("httpx.AsyncClient", mock_class):
        client = OpenF1Client(base_url="https://api.openf1.org/v1")
        await client.get_meetings(year=2023, country="Bahrain")
        mock_instance.get.assert_called_once()
        call_kwargs = mock_instance.get.call_args
        assert call_kwargs.kwargs["params"]["country_name"] == "Bahrain"


@pytest.mark.asyncio
async def test_get_meetings_timeout(mock_async_client):
    """Client raises OpenF1UnavailableError on timeout."""
    mock_class, mock_instance = mock_async_client
    mock_instance.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    with patch("httpx.AsyncClient", mock_class):
        client = OpenF1Client(base_url="https://api.openf1.org/v1")
        with pytest.raises(OpenF1UnavailableError):
            await client.get_meetings(year=2023)


@pytest.mark.asyncio
async def test_get_meetings_server_error(mock_async_client):
    """Client raises OpenF1UnavailableError on 500."""
    mock_class, mock_instance = mock_async_client
    mock_instance.get = AsyncMock(return_value=httpx.Response(500))
    with patch("httpx.AsyncClient", mock_class):
        client = OpenF1Client(base_url="https://api.openf1.org/v1")
        with pytest.raises(OpenF1UnavailableError):
            await client.get_meetings(year=2023)


@pytest.mark.asyncio
async def test_get_sessions_success(mock_async_client):
    """Client correctly fetches sessions for a meeting."""
    mock_class, mock_instance = mock_async_client
    mock_instance.get = AsyncMock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "session_key": 9158,
                    "session_name": "Race",
                    "session_type": "Race",
                    "date_start": "2023-03-05T15:00:00+00:00",
                    "date_end": "2023-03-05T17:00:00+00:00",
                }
            ],
        )
    )
    with patch("httpx.AsyncClient", mock_class):
        client = OpenF1Client(base_url="https://api.openf1.org/v1")
        result = await client.get_sessions(meeting_key=1219)
        assert len(result) == 1
        assert result[0]["session_key"] == 9158
