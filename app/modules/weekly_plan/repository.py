"""Weekly and monthly plan data access layer."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import TypeVar

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monthly_plan import MonthlyPlan
from app.models.user import User
from app.models.weekly_plan import WeeklyPlan


PlanModel = TypeVar("PlanModel", WeeklyPlan, MonthlyPlan)


def _iso_week_bounds(year: int, week: int) -> tuple[date, date]:
    monday = date.fromisocalendar(year, week, 1)
    friday = monday + timedelta(days=4)
    return monday, friday


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    month_start = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return month_start, next_month - timedelta(days=1)


class BasePlanRepository:
    model: type[WeeklyPlan] | type[MonthlyPlan]

    def __init__(self, db: AsyncSession, organization_id: str) -> None:
        self.db = db
        self.organization_id = uuid.UUID(organization_id)

    async def list_by_range(self, user_id: str, start_date: date, end_date: date) -> list[PlanModel]:
        result = await self.db.execute(
            select(self.model)
            .where(
                self.model.organization_id == self.organization_id,
                self.model.user_id == user_id,
                self.model.date >= start_date,
                self.model.date <= end_date,
                self.model.deleted_at.is_(None),
            )
            .order_by(self.model.date.asc())
        )
        return list(result.scalars().all())

    async def replace_range(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
        days: list[dict],
    ) -> list[PlanModel]:
        submitted_dates = [item["date"] for item in days]
        rows_to_upsert = [
            {
                "id": uuid.uuid4(),
                "organization_id": self.organization_id,
                "user_id": user_id,
                "date": item["date"],
                "work_location": item["work_location"],
                "project": item["project"],
            }
            for item in days
            if item["work_location"] is not None
        ]

        if submitted_dates:
            await self.db.execute(
                delete(self.model).where(
                    self.model.organization_id == self.organization_id,
                    self.model.user_id == user_id,
                    self.model.date.in_(submitted_dates),
                )
            )

        if rows_to_upsert:
            statement = insert(self.model).values(rows_to_upsert)
            statement = statement.on_conflict_do_update(
                index_elements=[
                    self.model.organization_id,
                    self.model.user_id,
                    self.model.date,
                ],
                set_={
                    "work_location": statement.excluded.work_location,
                    "project": statement.excluded.project,
                    "deleted_at": None,
                },
            )
            await self.db.execute(statement)

        await self.db.commit()
        return await self.list_by_range(user_id=user_id, start_date=start_date, end_date=end_date)


class WeeklyPlanRepository(BasePlanRepository):
    model = WeeklyPlan

    async def list_by_week(self, user_id: str, year: int, week: int) -> list[WeeklyPlan]:
        start_date, end_date = _iso_week_bounds(year, week)
        return await self.list_by_range(user_id=user_id, start_date=start_date, end_date=end_date)

    async def list_team_by_week(self, year: int, week: int) -> list[dict]:
        start_date, end_date = _iso_week_bounds(year, week)
        result = await self.db.execute(
            select(WeeklyPlan, User.name.label("user_name"))
            .outerjoin(User, User.id == WeeklyPlan.user_id)
            .where(
                WeeklyPlan.organization_id == self.organization_id,
                WeeklyPlan.date >= start_date,
                WeeklyPlan.date <= end_date,
                WeeklyPlan.deleted_at.is_(None),
            )
            .order_by(WeeklyPlan.user_id.asc(), WeeklyPlan.date.asc())
        )
        rows = result.all()
        return [
            {
                "id": plan.id,
                "organization_id": plan.organization_id,
                "user_id": plan.user_id,
                "user_name": user_name,
                "date": plan.date,
                "work_location": plan.work_location,
                "project": plan.project,
            }
            for plan, user_name in rows
        ]

    async def set_day(
        self,
        user_id: str,
        target_date: date,
        work_location: str,
        project: str | None,
    ) -> WeeklyPlan:
        entries = await self.replace_range(
            user_id=user_id,
            start_date=target_date,
            end_date=target_date,
            days=[
                {
                    "date": target_date,
                    "work_location": work_location,
                    "project": project,
                }
            ],
        )
        return entries[0]


class MonthlyPlanRepository(BasePlanRepository):
    model = MonthlyPlan

    async def list_by_month(self, user_id: str, year: int, month: int) -> list[MonthlyPlan]:
        start_date, end_date = _month_bounds(year, month)
        return await self.list_by_range(user_id=user_id, start_date=start_date, end_date=end_date)
