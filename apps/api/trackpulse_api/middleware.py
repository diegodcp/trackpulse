from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .observability import request_id_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self._header_name = header_name
        self._logger = logging.getLogger("trackpulse_api.request")

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get(self._header_name, str(uuid4()))
        token = request_id_context.set(request_id)
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            response.headers[self._header_name] = request_id
            self._logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else None,
                },
            )
            return response
        finally:
            request_id_context.reset(token)
