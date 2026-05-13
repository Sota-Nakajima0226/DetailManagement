import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import LOG_API_ACCESS
from app.core.logging import log_event


logger = logging.getLogger("app.api.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if not LOG_API_ACCESS:
            return await call_next(request)

        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.exception(
                "api_request_failed",
                extra={
                    "event_name": "api_request_failed",
                    "event_fields": _request_fields(request, request_id, 500, duration_ms),
                },
            )
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        log_event(
            logger,
            "api_request_completed",
            **_request_fields(
                request,
                request_id,
                response.status_code,
                duration_ms,
            ),
        )
        return response


def _request_fields(
    request: Request,
    request_id: str,
    status_code: int,
    duration_ms: float,
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "client_host": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
