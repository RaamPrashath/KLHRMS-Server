"""
KL HRMS v1 API router.
All HRMS module endpoints registered here.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    attendance,
    assets,
    developers,
    documents,
    employees,
    health,
    helpdesk,
    leaves,
    organization,
    payroll,
    payslips,
    projects,
    recruitment,
    reports,
    timesheet,
)

api_router = APIRouter()

# ── Infrastructure ────────────────────────────────────────────────────────────
api_router.include_router(health.router)

# ── HRMS Modules ──────────────────────────────────────────────────────────────
api_router.include_router(organization.router)
api_router.include_router(employees.router)
api_router.include_router(attendance.router)
api_router.include_router(leaves.router)
api_router.include_router(timesheet.router)
api_router.include_router(projects.router)
api_router.include_router(recruitment.router)
api_router.include_router(payroll.router)
api_router.include_router(payslips.router)
api_router.include_router(assets.router)
api_router.include_router(helpdesk.router)
api_router.include_router(documents.router)
api_router.include_router(reports.router)
api_router.include_router(developers.router)
