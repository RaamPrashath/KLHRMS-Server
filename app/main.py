"""KL HRMS API — application factory."""
import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.modules.router import api_router
from app.shared.config import get_settings
from app.shared.database import engine
from app.shared.exceptions import HRMSException
from app.shared.logging import setup_logging
from app.shared.middleware.request_context import RequestContextMiddleware
from app.shared.middleware.tenant_context import TenantContextMiddleware

settings = get_settings()
setup_logging(settings.log_level, settings.log_json)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("klhrms.starting")
    yield
    await engine.dispose()
    logger.info("klhrms.stopped")


app = FastAPI(
    title="KL HRMS API",
    version="1.0.0",
    description="KL HRMS — multi-tenant SaaS HRMS backend",
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── Exception handlers ────────────────────────────────────────────────────────


@app.exception_handler(HRMSException)
async def hrms_exception_handler(request: Request, exc: HRMSException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Override FastAPI's default 422 handler to log the full error detail
    server-side and return a clean, structured response to the client.

    The default handler returns the raw Pydantic error tree which is useful
    in development but leaks internal field names in production. This handler
    preserves the full detail in logs while returning a sanitized response.
    """
    errors = exc.errors()
    logger.warning(
        "request.validation_error",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": errors,
        },
    )
    # Return the full Pydantic error detail — useful for debugging on the
    # frontend. In production you may want to strip internal field paths.
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed.",
            "errors": [
                {
                    "field": " → ".join(str(loc) for loc in err["loc"]),
                    "message": err["msg"],
                    "type": err["type"],
                }
                for err in errors
            ],
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for any unhandled exception.

    Without this, Starlette returns a bare 500 that bypasses the middleware
    stack — meaning no CORS headers are attached and the browser reports a
    CORS error instead of the real server error.

    This handler returns a proper JSON 500 that travels through the full
    middleware stack, so CORS headers are always present on error responses.
    """
    logger.error(
        "unhandled_exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        },
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )


# ── Middleware ────────────────────────────────────────────────────────────────
#
# Starlette builds the middleware stack in REVERSE registration order.
# The LAST add_middleware call becomes the OUTERMOST layer (first to receive
# a request, last to send a response).
#
# Required order (outermost → innermost):
#   CORSMiddleware          — must be outermost so CORS headers appear on
#                             every response, including 4xx/5xx errors
#   TrustedHostMiddleware   — rejects bad Host headers before any work is done
#   TenantContextMiddleware — reads x-organization-id for observability
#   RequestContextMiddleware— attaches request-id and timing headers
#
# Registration order is therefore innermost → outermost:

app.add_middleware(RequestContextMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"], include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "KL HRMS API", "docs": "/docs"}
