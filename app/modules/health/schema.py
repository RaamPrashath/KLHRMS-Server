"""Health check response schemas."""
from pydantic import BaseModel


class ComponentHealth(BaseModel):
    component: str
    status: str  # "up" | "down"
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str  # "healthy" | "degraded"
    checks: list[ComponentHealth]
