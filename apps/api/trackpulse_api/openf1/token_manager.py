from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import httpx


class OpenF1TokenManager:
    """Manage OpenF1 OAuth token retrieval and short-lived caching."""

    def __init__(
        self,
        *,
        token_url: str,
        username: str,
        password: str,
        timeout_seconds: float = 10.0,
        cache_skew_seconds: int = 15,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token_url = token_url
        self._username = username
        self._password = password
        self._timeout_seconds = timeout_seconds
        self._cache_skew_seconds = cache_skew_seconds
        self._http_client = http_client
        self._access_token: str | None = None
        self._expires_at: datetime | None = None
        self._logger = logging.getLogger(__name__)

    async def get_token(self) -> str:
        now = datetime.now(timezone.utc)
        if self._access_token is not None and self._expires_at is not None and now < self._expires_at:
            return self._access_token

        token_payload = await self._fetch_token()
        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("OpenF1 token response did not include a valid access_token")

        expires_in = token_payload.get("expires_in")
        if isinstance(expires_in, (int, float)) and expires_in > self._cache_skew_seconds:
            ttl_seconds = int(expires_in) - self._cache_skew_seconds
        else:
            ttl_seconds = 60

        self._access_token = access_token
        self._expires_at = now + timedelta(seconds=ttl_seconds)
        self._logger.debug("Fetched OpenF1 OAuth token")
        return access_token

    async def _fetch_token(self) -> dict[str, Any]:
        data = {
            "username": self._username,
            "password": self._password,
        }

        if self._http_client is not None:
            response = await self._http_client.post(
                self._token_url,
                data=data,
                timeout=self._timeout_seconds,
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(self._token_url, data=data)

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("OpenF1 token response must be a JSON object")
        return payload
