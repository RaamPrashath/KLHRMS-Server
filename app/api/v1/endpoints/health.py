"""Health check — no auth required."""
import asyncio

from fastapi import APIRouter

from app.core.database import db_healthcheck
from app.core.redis import redis_healthcheck
from app.schemas.health import ComponentHealth, HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_ok, redis_ok = await asyncio.gather(db_healthcheck(), redis_healthcheck())
    checks = [
        ComponentHealth(component="postgres", status="up" if db_ok else "down"),
        ComponentHealth(component="redis", status="up" if redis_ok else "down"),
    ]
    overall = "healthy" if all(c.status == "up" for c in checks) else "degraded"
    return HealthResponse(status=overall, checks=checks)
