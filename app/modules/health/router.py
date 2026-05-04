"""Health check — no auth required."""
from fastapi import APIRouter

from app.modules.health.schema import ComponentHealth, HealthResponse
from app.shared.database import db_healthcheck

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
async def check_run() -> dict[str, str]:
    return {"status": "running"}
