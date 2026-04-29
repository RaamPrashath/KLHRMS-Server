"""Report generation endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/headcount")
async def headcount_report(auth: AuthContextDep):
    raise NotImplementedError


@router.get("/attendance-summary")
async def attendance_summary_report(auth: AuthContextDep):
    raise NotImplementedError


@router.get("/payroll-summary")
async def payroll_summary_report(auth: AuthContextDep):
    raise NotImplementedError


@router.post("/export")
async def export_report(auth: AuthContextDep):
    raise NotImplementedError
