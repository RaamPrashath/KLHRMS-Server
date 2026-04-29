"""Document management endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_documents(auth: AuthContextDep):
    raise NotImplementedError


@router.post("", status_code=201)
async def upload_document(auth: AuthContextDep):
    raise NotImplementedError


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str, auth: AuthContextDep):
    raise NotImplementedError
