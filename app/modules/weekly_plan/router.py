"""Weekly plan endpoints."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.modules.weekly_plan.repository import WeeklyPlanRepository
from app.modules.weekly_plan.schema import WeeklyPlanDayCreate, WeeklyPlanRead
from app.modules.weekly_plan.service import WeeklyPlanService
from app.shared.constants import ROLE_ADMIN, ROLE_HR, ROLE_MANAGER, ROLE_SUPER_ADMIN, ROLE_EMPLOYEE
from app.shared.deps.auth import AuthContextDep, DbSession, require_roles

router = APIRouter(prefix="/weekly-plans", tags=["weekly-plans"])


def get_service(db: DbSession, auth: AuthContextDep) -> WeeklyPlanService:
    repo = WeeklyPlanRepository(session=db, organization_id=auth.organization_id)
    return WeeklyPlanService(repo=repo, auth=auth)


ServiceDep = Annotated[WeeklyPlanService, Depends(get_service)]


@router.get(
    "",
    response_model=list[WeeklyPlanRead],
    status_code=status.HTTP_200_OK,
    summary="Get my weekly plan",
)
async def get_my_weekly_plan(
    year: int = Query(ge=2000, le=2100),
    week: int = Query(ge=1, le=53),
    service: ServiceDep = ...,
) -> list[WeeklyPlanRead]:
    """Return the current user's plan entries for the given ISO week."""
    return await service.get_my_week(year=year, week=week)


@router.get(
    "/team",
    response_model=list[WeeklyPlanRead],
    status_code=status.HTTP_200_OK,
    summary="Get team weekly plans",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE))],
)
async def get_team_weekly_plan(
    year: int = Query(ge=2000, le=2100),
    week: int = Query(ge=1, le=53),
    service: ServiceDep = ...,
) -> list[WeeklyPlanRead]:
    """Return all org members' plan entries for the given ISO week."""
    return await service.get_team_week(year=year, week=week)


@router.put(
    "/{plan_date}",
    response_model=WeeklyPlanRead,
    status_code=status.HTTP_200_OK,
    summary="Set a day's plan",
)
async def set_weekly_plan_day(
    plan_date: date,
    body: WeeklyPlanDayCreate,
    service: ServiceDep,
) -> WeeklyPlanRead:
    """Create or replace the plan entry for a specific weekday."""
    return await service.set_day(
        target_date=plan_date,
        work_location=body.work_location,
        project=body.project,
    )
