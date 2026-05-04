"""KL HRMS API — application factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
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


# ── Middleware (outermost → innermost) ────────────────────────────────────────

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
