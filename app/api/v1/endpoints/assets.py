"""Asset management endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
async def list_assets(auth: AuthContextDep):
    raise NotImplementedError


@router.post("", status_code=201)
async def create_asset(auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{asset_id}/assign")
async def assign_asset(asset_id: str, auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{asset_id}/return")
async def return_asset(asset_id: str, auth: AuthContextDep):
    raise NotImplementedError
