"""Recruitment endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/recruitment", tags=["recruitment"])


@router.get("")
async def list_jobs(auth: AuthContextDep):
    raise NotImplementedError


@router.post("", status_code=201)
async def create_job(auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{job_id}")
async def update_job(job_id: str, auth: AuthContextDep):
    raise NotImplementedError
