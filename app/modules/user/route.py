from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.schema import SetPasswordRequest, SetPasswordResponse
from app.modules.user.service import set_password as set_password_service
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/set-password", response_model=SetPasswordResponse)
async def set_password(
    body: SetPasswordRequest,
    ctx: Annotated[MemberContext, Depends(get_member_context)],
    db: AsyncSession = Depends(get_db),
) -> SetPasswordResponse:
    result = await set_password_service(
        member_id=ctx.member.id,
        organization_id=ctx.organization.id,
        new_password=body.new_password,
        db=db,
    )
    return SetPasswordResponse(**result)
