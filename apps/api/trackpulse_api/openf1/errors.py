from __future__ import annotations

from .models import SessionDiscoveryQuery


class OpenF1RequestError(RuntimeError):
    """Raised when an OpenF1 request fails after retries."""


class SessionNotFoundError(LookupError):
    def __init__(self, query: SessionDiscoveryQuery) -> None:
        self.query = query
        super().__init__(
            "No OpenF1 session found for "
            f"year={query.year}, country_name={query.country_name!r}, session_name={query.session_name!r}"
        )
