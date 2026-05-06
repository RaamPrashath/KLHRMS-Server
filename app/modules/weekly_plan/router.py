"""Weekly plan endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.weekly_plan.permissions import (
    WeeklyPlanAccessContext,
    require_weekly_plan_permission,
)
from app.modules.weekly_plan.repository import MonthlyPlanRepository, WeeklyPlanRepository
from app.modules.weekly_plan.schema import (
    PlanLocationOptionRead,
    WeeklyPlanBulkSaveRequest,
    WeeklyPlanDayCreate,
    WeeklyPlanRead,
    build_location_options,
)
from app.modules.weekly_plan.service import WeeklyPlanService
from app.shared.database import get_async_db

router = APIRouter(prefix="/weekly-plans", tags=["weekly-plans"])


def build_service(db: AsyncSession, auth: WeeklyPlanAccessContext) -> WeeklyPlanService:
    return WeeklyPlanService(
        weekly_repo=WeeklyPlanRepository(db=db, organization_id=auth.organization.id),
        monthly_repo=MonthlyPlanRepository(db=db, organization_id=auth.organization.id),
        auth=auth,
    )


@router.get(
    "/locations",
    response_model=list[PlanLocationOptionRead],
    status_code=status.HTTP_200_OK,
    summary="Get plan locations",
)
async def get_plan_locations() -> list[PlanLocationOptionRead]:
    return build_location_options()


@router.get(
    "",
    response_model=list[WeeklyPlanRead],
    status_code=status.HTTP_200_OK,
    summary="Get my weekly plan",
)
async def get_my_weekly_plan(
    year: int = Query(ge=2000, le=2100),
    week: int = Query(ge=1, le=53),
    db: AsyncSession = Depends(get_async_db),
    auth: WeeklyPlanAccessContext = Depends(require_weekly_plan_permission("view")),
) -> list[WeeklyPlanRead]:
    return await build_service(db, auth).get_my_week(year=year, week=week)


@router.get(
    "/month",
    response_model=list[WeeklyPlanRead],
    status_code=status.HTTP_200_OK,
    summary="Get my monthly plan",
)
async def get_my_monthly_plan(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    db: AsyncSession = Depends(get_async_db),
    auth: WeeklyPlanAccessContext = Depends(require_weekly_plan_permission("view")),
) -> list[WeeklyPlanRead]:
    return await build_service(db, auth).get_my_month(year=year, month=month)


@router.get(
    "/team",
    response_model=list[WeeklyPlanRead],
    status_code=status.HTTP_200_OK,
    summary="Get team weekly plans",
)
async def get_team_weekly_plan(
    year: int = Query(ge=2000, le=2100),
    week: int = Query(ge=1, le=53),
    db: AsyncSession = Depends(get_async_db),
    auth: WeeklyPlanAccessContext = Depends(require_weekly_plan_permission("view")),
) -> list[WeeklyPlanRead]:
    return await build_service(db, auth).get_team_week(year=year, week=week)


@router.put(
    "/{plan_date}",
    response_model=WeeklyPlanRead,
    status_code=status.HTTP_200_OK,
    summary="Set a day's plan",
)
async def set_weekly_plan_day(
    plan_date: date,
    body: WeeklyPlanDayCreate,
    db: AsyncSession = Depends(get_async_db),
    auth: WeeklyPlanAccessContext = Depends(require_weekly_plan_permission("edit")),
) -> WeeklyPlanRead:
    return await build_service(db, auth).set_day(
        target_date=plan_date,
        work_location=body.work_location,
        project=body.project,
    )


@router.post(
    "/week",
    response_model=list[WeeklyPlanRead],
    status_code=status.HTTP_200_OK,
    summary="Save a weekly plan",
)
async def save_weekly_plan(
    body: WeeklyPlanBulkSaveRequest,
    year: int = Query(ge=2000, le=2100),
    week: int = Query(ge=1, le=53),
    db: AsyncSession = Depends(get_async_db),
    auth: WeeklyPlanAccessContext = Depends(require_weekly_plan_permission("edit")),
) -> list[WeeklyPlanRead]:
    return await build_service(db, auth).save_week(year=year, week=week, body=body)


@router.post(
    "/month",
    response_model=list[WeeklyPlanRead],
    status_code=status.HTTP_200_OK,
    summary="Save a monthly plan",
)
async def save_monthly_plan(
    body: WeeklyPlanBulkSaveRequest,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    db: AsyncSession = Depends(get_async_db),
    auth: WeeklyPlanAccessContext = Depends(require_weekly_plan_permission("edit")),
) -> list[WeeklyPlanRead]:
    return await build_service(db, auth).save_month(year=year, month=month, body=body)
