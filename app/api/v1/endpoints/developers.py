"""Developer API token management endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/developers", tags=["developers"])


@router.get("/tokens")
async def list_tokens(auth: AuthContextDep):
    raise NotImplementedError


@router.post("/tokens", status_code=201)
async def create_token(auth: AuthContextDep):
    raise NotImplementedError


@router.delete("/tokens/{token_id}", status_code=204)
async def revoke_token(token_id: str, auth: AuthContextDep):
    raise NotImplementedError
