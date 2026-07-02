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
    async def get_location(
        self,
        session_key: int,
        driver_number: int | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
    ) -> list[dict]: ...
    async def get_laps(
        self,
        session_key: int,
        driver_number: int | None = None,
    ) -> list[dict]: ...
    async def get_car_data(self, session_key: int, driver_number: int | None = None) -> list[dict]: ...
    async def get_weather(self, session_key: int) -> list[dict]: ...
    async def get_stints(self, session_key: int) -> list[dict]: ...
    async def get_race_control(self, session_key: int) -> list[dict]: ...
    async def get_intervals(self, session_key: int) -> list[dict]: ...
    async def get_positions(self, session_key: int) -> list[dict]: ...
    async def get_pit_stops(self, session_key: int) -> list[dict]: ...
    async def get_drivers(self, session_key: int) -> list[dict]: ...


class OpenF1Client:
    """Concrete HTTP client for OpenF1 API."""

    def __init__(self, base_url: str, timeout: float = 120.0):
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

    async def get_location(
        self,
        session_key: int,
        driver_number: int | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
    ) -> list[dict]:
        """GET /location?session_key={key}&driver_number={driver}"""
        params: dict[str, int | str] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        if date_start:
            params["date>"] = date_start
        if date_end:
            params["date<"] = date_end
        return await self._get("/location", params)

    async def get_car_data(
        self,
        session_key: int,
        driver_number: int | None = None,
    ) -> list[dict]:
        """GET /car_data?session_key={key}"""
        params: dict[str, int | str] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return await self._get("/car_data", params)

    async def get_weather(self, session_key: int) -> list[dict]:
        """GET /weather?session_key={key}"""
        return await self._get("/weather", {"session_key": session_key})

    async def get_laps(
        self,
        session_key: int,
        driver_number: int | None = None,
    ) -> list[dict]:
        """GET /laps?session_key={key}&driver_number={driver}"""
        params: dict[str, int | str] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return await self._get("/laps", params)

    async def get_stints(self, session_key: int) -> list[dict]:
        """GET /stints?session_key={key}"""
        return await self._get("/stints", {"session_key": session_key})

    async def get_race_control(self, session_key: int) -> list[dict]:
        """GET /race_control?session_key={key}"""
        return await self._get("/race_control", {"session_key": session_key})

    async def get_intervals(self, session_key: int) -> list[dict]:
        """GET /intervals?session_key={key}"""
        return await self._get("/intervals", {"session_key": session_key})

    async def get_positions(self, session_key: int) -> list[dict]:
        """GET /position?session_key={key}"""
        return await self._get("/position", {"session_key": session_key})

    async def get_pit_stops(self, session_key: int) -> list[dict]:
        """GET /pit?session_key={key}"""
        return await self._get("/pit", {"session_key": session_key})

    async def get_drivers(self, session_key: int) -> list[dict]:
        """GET /drivers?session_key={key}"""
        return await self._get("/drivers", {"session_key": session_key})

    async def _get(self, path: str, params: dict) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}{path}", params=params)
                if response.status_code in (404, 422):
                    return []  # OpenF1 returns 404/422 when no data exists or params are invalid
                if response.status_code != 200:
                    raise OpenF1UnavailableError(
                        f"OpenF1 returned status {response.status_code}"
                    )
                return response.json()
        except httpx.TimeoutException as exc:
            raise OpenF1UnavailableError("OpenF1 request timed out") from exc
        except httpx.HTTPError as exc:
            raise OpenF1UnavailableError(f"OpenF1 HTTP error: {exc}") from exc
