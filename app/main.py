import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.endpoints import health
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import HRMSException
from app.core.logging import setup_logging
from app.middleware.audit_log import AuditLogMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.tenant_context import TenantContextMiddleware

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
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"], include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "KL HRMS API", "docs": "/docs"}
