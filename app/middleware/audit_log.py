"""
Audit log middleware.
Captures mutating requests (POST/PUT/PATCH/DELETE) and queues
an audit log entry after the response is sent.
Full before/after snapshots are written by the service layer.
This middleware records the HTTP-level audit trail only.
"""
import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.constants import HEADER_REQUEST_ID

logger = logging.getLogger(__name__)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        if request.method in MUTATING_METHODS and response.status_code < 400:
            request_id = request.headers.get(HEADER_REQUEST_ID, str(uuid.uuid4()))
            logger.info(
                "audit.http",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "organization_id": str(getattr(request.state, "organization_id", None)),
                },
            )

        return response
