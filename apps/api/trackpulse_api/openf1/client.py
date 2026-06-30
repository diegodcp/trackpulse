from __future__ import annotations

from collections.abc import Sequence
from datetime import timezone
import logging

import httpx

from .errors import SessionNotFoundError
from .models import OpenF1Session, SessionDiscoveryQuery


class OpenF1HistoricalClient:
    def __init__(
        self,
        *,
        base_url: str = "https://api.openf1.org",
        timeout_seconds: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client
        self._logger = logging.getLogger(__name__)

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

        if self._http_client is not None:
            response = await self._http_client.get(
                f"{self._base_url}/v1/sessions",
                params=params,
                timeout=self._timeout_seconds,
            )
        else:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.get("/v1/sessions", params=params)

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("OpenF1 sessions endpoint returned a non-list payload")
        return payload

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
