import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.shared.constants import HEADER_TENANT_ID

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        raw = request.headers.get(HEADER_TENANT_ID)

        request.state.organization_id = None

        if raw:
            try:
                request.state.organization_id = uuid.UUID(raw)
            except ValueError:
                logger.warning(
                    "invalid.organization_id_header",
                    extra={
                        "header_value": raw,
                        "path": request.url.path,
                    },
                )

        return await call_next(request)