"""
KL HRMS API — FastAPI application entry point.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.modules.ai_scoring.route import router as ai_scoring_router
from app.modules.access_control.route import router as access_control_router
from app.modules.assets.route import router as assets_router
from app.modules.attendance.route import router as attendance_router
from app.modules.candidates.public_route import router as candidates_public_router
from app.modules.candidates.route import router as candidates_router
from app.modules.departments.route import router as departments_router
from app.modules.employee.route import router as employee_router
from app.modules.hiring_teams.route import router as hiring_teams_router
from app.modules.holiday_sync.route import router as holiday_sync_router
from app.modules.jobs.route import router as jobs_router
from app.modules.leave.route import router as leave_router
from app.modules.offers.public_route import router as public_offers_router
from app.modules.offers.route import router as offers_router
from app.modules.procurement.route import router as procurement_router
from app.modules.projects.route import router as projects_router
from app.modules.onboarding.public_route import router as public_onboarding_router
from app.modules.onboarding.route import router as onboarding_router
from app.modules.role.route import router as role_router
from app.modules.weekly_plan.router import router as weekly_plan_router
from app.shared.config import get_settings
from app.shared.scheduler import register_jobs, scheduler

settings = get_settings()
UPLOADS_DIR = Path(__file__).resolve().parents[1] / ".uploads"


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start the APScheduler on startup and shut it down on exit."""
    register_jobs()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="KL HRMS API",
    version="1.0.0",
    description="KL HRMS — multi-tenant SaaS HRMS backend",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(onboarding_router)
app.include_router(public_onboarding_router)
app.include_router(role_router)
app.include_router(attendance_router)
app.include_router(candidates_public_router)
app.include_router(candidates_router)
app.include_router(ai_scoring_router)
app.include_router(jobs_router)
app.include_router(offers_router)
app.include_router(public_offers_router)
app.include_router(leave_router)
app.include_router(projects_router)
app.include_router(access_control_router)
app.include_router(assets_router)
app.include_router(procurement_router)
app.include_router(departments_router)
app.include_router(holiday_sync_router)
app.include_router(weekly_plan_router, prefix=settings.api_v1_prefix)
app.include_router(hiring_teams_router)
app.include_router(employee_router)


@app.get("/", tags=["root"], include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "KL HRMS API", "docs": "/docs"}
