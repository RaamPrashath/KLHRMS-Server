"""Leave management endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/leaves", tags=["leaves"])


@router.get("")
async def list_leaves(auth: AuthContextDep):
    raise NotImplementedError


@router.post("", status_code=201)
async def apply_leave(auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{leave_id}/approve")
async def approve_leave(leave_id: str, auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{leave_id}/reject")
async def reject_leave(leave_id: str, auth: AuthContextDep):
    raise NotImplementedError
