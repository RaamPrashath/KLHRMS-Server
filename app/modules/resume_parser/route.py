from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resume_parser.schema import (
    ResumeParserHistoryResponse,
    ResumeParserProcessResponse,
    TemplateType,
)
from app.modules.resume_parser.service import list_resume_parser_history, process_resume_files
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/resume-parser", tags=["resume-parser"])


@router.post("/process", response_model=ResumeParserProcessResponse)
async def process_resumes(
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "view", allow_self=True))],
    resume_files: Annotated[list[UploadFile], File(...)],
    template_type: Annotated[TemplateType, Form()] = "default",
    db: AsyncSession = Depends(get_db),
) -> ResumeParserProcessResponse:
    return await process_resume_files(
        db=db,
        organization_id=ctx.organization.id,
        member_id=ctx.member.id,
        files=resume_files,
        template_type=template_type,
    )


@router.get("/history", response_model=ResumeParserHistoryResponse)
async def get_resume_parser_history(
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "view", allow_self=True))],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=200),
) -> ResumeParserHistoryResponse:
    return await list_resume_parser_history(
        db=db,
        organization_id=ctx.organization.id,
        member_id=ctx.member.id,
        scope=getattr(ctx, "scope", None),
        limit=limit,
    )
