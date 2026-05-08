"""
Holiday sync route.

POST /leaves/holidays/sync
  — Manual sync trigger. Resolves the organization from the standard
    x-organization-slug / x-membership-id headers, exactly as every
    other HRMS route does. Requires leaves.create at organization scope.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.holiday_sync.schema import HolidaySyncResponse
from app.modules.holiday_sync.service import run_org_sync
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leaves", tags=["leaves"])


@router.post(
    "/holidays/sync",
    status_code=status.HTTP_200_OK,
    summary="Sync public holidays for the authenticated organization",
    description=(
        "Populates the organization's Holiday table from the PublicHolidayMaster "
        "for the current year. If the master table is empty it fetches from the "
        "Calendarific API first. Requires leaves.create at organization scope."
    ),
)
async def sync_org_holidays(
    ctx: Annotated[
        MemberContext,
        Depends(require_permission("leaves", "create")),
    ],
    db: AsyncSession = Depends(get_db),
) -> HolidaySyncResponse:
    year = dt.date.today().year

    try:
        result = await run_org_sync(
            organization_id=ctx.organization.id,
            year=year,
            db=db,
        )
    except Exception as exc:
        logger.exception(
            "Holiday sync failed for org=%s year=%d",
            ctx.organization.id,
            year,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Holiday sync failed: {exc}",
        ) from exc

    return HolidaySyncResponse(
        year=result["year"],
        organization_id=result["organization_id"],
        rows_inserted=result["rows_inserted"],
        source=result["source"],
    )
