"""
Global FastAPI exception handler — catches all unhandled exceptions,
logs the full traceback safely, and returns a sanitized 500 response.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "Unhandled exception during request processing",
        extra={"context": {"path": request.url.path, "method": request.method}},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred."},
    )
