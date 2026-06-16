from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.document_collection import service
from app.modules.document_collection.schema import (
    DocumentCollectionPublicRead,
    DocumentCollectionSubmitRequest,
    DocumentCollectionSubmitResponse,
)
from app.shared.database import get_db

router = APIRouter(prefix="/public/document-collection", tags=["public-document-collection"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/{token}", response_model=DocumentCollectionPublicRead)
async def get_document_collection(
    token: str,
    db: DbSession,
) -> DocumentCollectionPublicRead:
    return await service.get_public_request(db, token)


@router.post("/{token}/submit", response_model=DocumentCollectionSubmitResponse)
async def submit_document_collection(
    token: str,
    body: DocumentCollectionSubmitRequest,
    db: DbSession,
) -> DocumentCollectionSubmitResponse:
    return await service.submit_public_request(db, token, body)
