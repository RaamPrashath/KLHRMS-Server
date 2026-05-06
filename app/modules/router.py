"""
Central v1 API router.
Register every module router here as new modules are built.
"""
from fastapi import APIRouter

from app.modules.health.router import router as health_router
from app.modules.weekly_plan.router import router as weekly_plan_router

api_router = APIRouter()

# ── Infrastructure ────────────────────────────────────────────────────────────
api_router.include_router(health_router)

# ── HRMS Modules ──────────────────────────────────────────────────────────────
api_router.include_router(weekly_plan_router)
# Add new module routers here:
# api_router.include_router(employees_router)
# api_router.include_router(attendance_router)
