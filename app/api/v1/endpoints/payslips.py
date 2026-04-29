"""Payslip endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/payslips", tags=["payslips"])


@router.get("")
async def list_payslips(auth: AuthContextDep):
    raise NotImplementedError


@router.get("/{payslip_id}")
async def get_payslip(payslip_id: str, auth: AuthContextDep):
    raise NotImplementedError


@router.get("/{payslip_id}/pdf")
async def download_payslip_pdf(payslip_id: str, auth: AuthContextDep):
    raise NotImplementedError
