"""Health check — no auth required."""
import asyncio

from fastapi import APIRouter

from app.core.database import db_healthcheck
from app.schemas.health import ComponentHealth, HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_ok = await db_healthcheck()
    checks = [
        ComponentHealth(component="postgres", status="up" if db_ok else "down"),
    ]
    overall = "healthy" if all(c.status == "up" for c in checks) else "degraded"
    return HealthResponse(status=overall, checks=checks)


@router.get("/check")
async def check_run():
    try:
        return {"status": "running"}
    except Exception as e:
        return {"status": "error", "message": str(e)}