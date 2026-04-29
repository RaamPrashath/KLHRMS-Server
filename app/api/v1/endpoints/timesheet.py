"""Timesheet endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


@router.get("")
async def list_timesheets(auth: AuthContextDep):
    raise NotImplementedError


@router.post("", status_code=201)
async def create_timesheet(auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{timesheet_id}/submit")
async def submit_timesheet(timesheet_id: str, auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{timesheet_id}/approve")
async def approve_timesheet(timesheet_id: str, auth: AuthContextDep):
    raise NotImplementedError
