"""Organization settings endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/organization", tags=["organization"])


@router.get("/settings")
async def get_org_settings(auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/settings")
async def update_org_settings(auth: AuthContextDep):
    raise NotImplementedError
