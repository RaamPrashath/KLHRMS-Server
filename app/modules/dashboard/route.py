from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.schema import DashboardResponse
from app.modules.dashboard.service import get_dashboard
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def read_dashboard(
    ctx: Annotated[MemberContext, Depends(get_member_context)],
    db: AsyncSession = Depends(get_db),
    today: dt.date = Query(...),
) -> DashboardResponse:
    return await get_dashboard(db, ctx, today)
