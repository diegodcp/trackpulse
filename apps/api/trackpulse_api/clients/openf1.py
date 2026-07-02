from typing import Protocol

import httpx


class OpenF1UnavailableError(Exception):
    """Raised when the OpenF1 API is unreachable or returns an error."""

    def __init__(self, detail: str = "OpenF1 API is unavailable"):
        self.detail = detail
        super().__init__(detail)


class OpenF1ClientProtocol(Protocol):
    """Interface for OpenF1 API communication."""

    async def get_meetings(self, year: int, country: str | None = None) -> list[dict]: ...
    async def get_sessions(self, meeting_key: int) -> list[dict]: ...


class OpenF1Client:
    """Concrete HTTP client for OpenF1 API."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_meetings(self, year: int, country: str | None = None) -> list[dict]:
        """GET /meetings?year={year}&country_name={country}"""
        params: dict[str, int | str] = {"year": year}
        if country:
            params["country_name"] = country
        return await self._get("/meetings", params)

    async def get_sessions(self, meeting_key: int) -> list[dict]:
        """GET /sessions?meeting_key={meeting_key}"""
        return await self._get("/sessions", {"meeting_key": meeting_key})

    async def _get(self, path: str, params: dict) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}{path}", params=params)
                if response.status_code != 200:
                    raise OpenF1UnavailableError(
                        f"OpenF1 returned status {response.status_code}"
                    )
                return response.json()
        except httpx.TimeoutException as exc:
            raise OpenF1UnavailableError("OpenF1 request timed out") from exc
        except httpx.HTTPError as exc:
            raise OpenF1UnavailableError(f"OpenF1 HTTP error: {exc}") from exc
