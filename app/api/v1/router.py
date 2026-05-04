"""
KL HRMS v1 API router.
Modules are added here incrementally as they are built.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    weekly_plan,
)

api_router = APIRouter()

# ── Infrastructure ────────────────────────────────────────────────────────────
api_router.include_router(health.router)

# ── HRMS Modules ──────────────────────────────────────────────────────────────
api_router.include_router(weekly_plan.router)
# Note: employees and attendance endpoints removed per request
