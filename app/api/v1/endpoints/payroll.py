"""Payroll run endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/payroll", tags=["payroll"])


@router.get("")
async def list_payroll_runs(auth: AuthContextDep):
    raise NotImplementedError


@router.post("", status_code=201)
async def create_payroll_run(auth: AuthContextDep):
    raise NotImplementedError


@router.post("/{payroll_id}/process")
async def process_payroll(payroll_id: str, auth: AuthContextDep):
    raise NotImplementedError
