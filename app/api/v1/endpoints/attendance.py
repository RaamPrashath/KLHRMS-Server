"""Attendance endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("")
async def list_attendance(auth: AuthContextDep):
    raise NotImplementedError


@router.post("", status_code=201)
async def mark_attendance(auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{attendance_id}")
async def update_attendance(attendance_id: str, auth: AuthContextDep):
    raise NotImplementedError
