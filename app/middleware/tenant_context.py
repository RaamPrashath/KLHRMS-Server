"""
Tenant context middleware.
Reads x-organization-id header and stores it in request.state
for downstream logging and audit use.
The authoritative organization_id always comes from the verified
auth context (auth dependency), not this header.
This middleware is for observability only.
"""
import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.constants import HEADER_TENANT_ID

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        raw = request.headers.get(HEADER_TENANT_ID)
        if raw:
            try:
                request.state.organization_id = uuid.UUID(raw)
            except ValueError:
                request.state.organization_id = None
        else:
            request.state.organization_id = None

        return await call_next(request)
