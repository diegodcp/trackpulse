from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import timezone
import json
import logging
from pathlib import Path
from typing import Any, Literal

import httpx

from .errors import OpenF1RequestError, SessionNotFoundError
from .models import OpenF1Location, OpenF1Session, OpenF1Weather, SessionDiscoveryQuery


class OpenF1HistoricalClient:
    def __init__(
        self,
        *,
        base_url: str = "https://api.openf1.org",
        mode: Literal["fixture", "historical", "live"] = "historical",
        bearer_token: str | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        fixture_data_dir: str | Path | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._mode = mode
        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._fixture_data_dir = Path(fixture_data_dir) if fixture_data_dir is not None else None
        self._http_client = http_client
        self._logger = logging.getLogger(__name__)

    async def get_weather(
        self,
        *,
        session_key: int | None = None,
        limit: int | None = None,
    ) -> list[OpenF1Weather]:
        params: dict[str, int] = {}
        if session_key is not None:
            params["session_key"] = session_key
        if limit is not None:
            params["_limit"] = limit
        payload = await self._get_list("/v1/weather", params=params)
        return [OpenF1Weather.model_validate(item) for item in payload]

    async def get_location(
        self,
        *,
        session_key: int,
        driver_number: int | None = None,
        limit: int | None = None,
    ) -> list[OpenF1Location]:
        params: dict[str, int] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        if limit is not None:
            params["_limit"] = limit

        payload = await self._get_list("/v1/location", params=params)
        return [OpenF1Location.model_validate(item) for item in payload]

    async def get_location_batch(
        self,
        *,
        session_key: int,
        driver_numbers: Sequence[int],
        limit: int | None = None,
    ) -> dict[int, list[OpenF1Location]]:
        unique_driver_numbers = sorted(set(driver_numbers))
        if not unique_driver_numbers:
            return {}

        responses = await asyncio.gather(
            *[
                self.get_location(
                    session_key=session_key,
                    driver_number=driver_number,
                    limit=limit,
                )
                for driver_number in unique_driver_numbers
            ]
        )
        return {
            driver_number: records
            for driver_number, records in zip(unique_driver_numbers, responses, strict=True)
        }

    async def discover_session(self, query: SessionDiscoveryQuery) -> OpenF1Session:
        payload = await self._get_sessions(query)
        sessions = [OpenF1Session.model_validate(item) for item in payload]

        if not sessions:
            raise SessionNotFoundError(query)

        if len(sessions) == 1:
            return sessions[0]

        selected = self._select_deterministic_session(sessions, query.session_name)
        self._logger.warning(
            "Multiple OpenF1 sessions matched query; selected deterministic candidate"
        )
        return selected

    async def _get_sessions(self, query: SessionDiscoveryQuery) -> list[dict[str, object]]:
        params = query.model_dump(mode="json")
        return await self._get_list("/v1/sessions", params=params)

    async def _get_list(self, path: str, *, params: dict[str, Any]) -> list[dict[str, Any]]:
        if self._mode == "fixture":
            return self._load_fixture(path)

        headers = self._build_headers()
        self._logger.debug(
            "OpenF1 GET %s params=%s headers=%s",
            path,
            params,
            self._redacted_headers(headers),
        )

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                await asyncio.sleep(self._retry_backoff_seconds * (2 ** (attempt - 1)))

            try:
                response = await self._request(path, params=params, headers=headers)

                if response.status_code == 429 or response.status_code >= 500:
                    last_exc = httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    continue

                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    raise ValueError("OpenF1 endpoint returned a non-list payload")
                return payload
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc

        raise OpenF1RequestError(
            f"GET {path} failed after {self._max_retries + 1} attempts"
        ) from last_exc

    async def _request(
        self,
        path: str,
        *,
        params: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.get(
                f"{self._base_url}{path}",
                params=params,
                timeout=self._timeout_seconds,
                headers=headers,
            )

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
        ) as client:
            return await client.get(path, params=params, headers=headers)

    def _load_fixture(self, path: str) -> list[dict[str, Any]]:
        if self._fixture_data_dir is None:
            raise ValueError("fixture_data_dir must be configured when mode='fixture'")

        endpoint_name = path.rsplit("/", 1)[-1]
        fixture_path = self._fixture_data_dir / f"{endpoint_name}.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))

        if not isinstance(payload, list):
            raise ValueError(f"Fixture file {fixture_path} must contain a JSON list")
        if any(not isinstance(item, dict) for item in payload):
            raise ValueError(f"Fixture file {fixture_path} must contain a list of JSON objects")
        return payload

    def _build_headers(self) -> dict[str, str]:
        if not self._bearer_token:
            return {}
        return {"Authorization": f"Bearer {self._bearer_token}"}

    @staticmethod
    def _redacted_headers(headers: dict[str, str]) -> dict[str, str]:
        redacted = dict(headers)
        if "Authorization" in redacted:
            redacted["Authorization"] = "Bearer [REDACTED]"
        return redacted

    def _select_deterministic_session(
        self,
        sessions: Sequence[OpenF1Session],
        requested_session_name: str,
    ) -> OpenF1Session:
        exact_matches = [session for session in sessions if session.session_name == requested_session_name]
        candidates = exact_matches or list(sessions)

        return min(
            candidates,
            key=lambda session: (
                self._date_sort_key(session),
                session.session_key,
            ),
        )

    @staticmethod
    def _date_sort_key(session: OpenF1Session) -> float:
        if session.date_start is None:
            return float("inf")

        date_start = session.date_start
        if date_start.tzinfo is None:
            date_start = date_start.replace(tzinfo=timezone.utc)

        return date_start.timestamp()
