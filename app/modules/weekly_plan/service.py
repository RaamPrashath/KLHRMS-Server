"""Weekly plan business logic."""

from __future__ import annotations

from datetime import date
from collections import defaultdict
from typing import Iterable

from fastapi import HTTPException

from app.models.monthly_plan import MonthlyPlan
from app.models.weekly_plan import WeeklyPlan
from app.modules.weekly_plan.locations import PlanLocationValue
from app.modules.weekly_plan.permissions import WeeklyPlanAccessContext
from app.modules.weekly_plan.repository import MonthlyPlanRepository, WeeklyPlanRepository
from app.modules.weekly_plan.schema import (
    WeeklyPlanBulkSaveRequest,
    WeeklyPlanRead,
    validate_weekday,
)


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    next_month = date(year, month + 1, 1)
    return date.fromordinal(next_month.toordinal() - 1)


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


class WeeklyPlanService:
    def __init__(
        self,
        weekly_repo: WeeklyPlanRepository,
        monthly_repo: MonthlyPlanRepository,
        auth: WeeklyPlanAccessContext,
    ) -> None:
        self.weekly_repo = weekly_repo
        self.monthly_repo = monthly_repo
        self.auth = auth

    def _merge_entries_by_date(
        self,
        weekly_entries: Iterable[WeeklyPlan],
        monthly_entries: Iterable[MonthlyPlan],
    ) -> list[WeeklyPlan | MonthlyPlan]:
        merged_by_date: dict[date, WeeklyPlan | MonthlyPlan] = {}

        for entry in list(monthly_entries) + list(weekly_entries):
            current = merged_by_date.get(entry.date)
            if current is None or entry.updatedAt >= current.updatedAt:
                merged_by_date[entry.date] = entry

        return [merged_by_date[key] for key in sorted(merged_by_date)]

    async def _sync_weekly_days_to_monthly(self, days: list[dict], commit: bool = True) -> None:
        days_by_month: dict[tuple[int, int], list[dict]] = defaultdict(list)
        for day in days:
            month_key = (day["date"].year, day["date"].month)
            days_by_month[month_key].append(day)

        for (year, month), month_days in days_by_month.items():
            await self.monthly_repo.replace_range(
                user_id=self.auth.user.id,
                start_date=_month_start(year, month),
                end_date=_month_end(year, month),
                days=month_days,
                commit=False,
            )

        if commit:
            await self.monthly_repo.db.commit()

    async def _sync_monthly_days_to_weekly(self, days: list[dict], commit: bool = True) -> None:
        days_by_week: dict[tuple[int, int], list[dict]] = defaultdict(list)
        for day in days:
            iso = day["date"].isocalendar()
            week_key = (iso.year, iso.week)
            days_by_week[week_key].append(day)

        for (year, week), week_days in days_by_week.items():
            monday = date.fromisocalendar(year, week, 1)
            friday = date.fromisocalendar(year, week, 5)
            await self.weekly_repo.replace_range(
                user_id=self.auth.user.id,
                start_date=monday,
                end_date=friday,
                days=week_days,
                commit=False,
            )

        if commit:
            await self.weekly_repo.db.commit()

    async def get_my_week(self, year: int, week: int) -> list[WeeklyPlanRead]:
        monthly_monday = date.fromisocalendar(year, week, 1)
        monthly_friday = date.fromisocalendar(year, week, 5)
        weekly_entries = await self.weekly_repo.list_by_week(
            user_id=self.auth.user.id,
            year=year,
            week=week,
        )
        monthly_entries = await self.monthly_repo.list_by_range(
            user_id=self.auth.user.id,
            start_date=monthly_monday,
            end_date=monthly_friday,
        )
        entries = self._merge_entries_by_date(weekly_entries, monthly_entries)
        return [WeeklyPlanRead.model_validate(entry) for entry in entries]

    async def get_my_month(self, year: int, month: int) -> list[WeeklyPlanRead]:
        month_start = _month_start(year, month)
        month_end = _month_end(year, month)
        weekly_entries = await self.weekly_repo.list_by_range(
            user_id=self.auth.user.id,
            start_date=month_start,
            end_date=month_end,
        )
        monthly_entries = await self.monthly_repo.list_by_month(
            user_id=self.auth.user.id,
            year=year,
            month=month,
        )
        entries = self._merge_entries_by_date(weekly_entries, monthly_entries)
        return [WeeklyPlanRead.model_validate(entry) for entry in entries]

    async def get_team_month(self, year: int, month: int) -> list[WeeklyPlanRead]:
        if self.auth.permission_scope != "organization":
            raise HTTPException(status_code=403, detail="Organization scope is required for team plans")

        entries = await self.weekly_repo.list_team_by_range(
            start_date=_month_start(year, month),
            end_date=_month_end(year, month),
        )
        return [
            WeeklyPlanRead(
                id=entry["id"],
                organization_id=entry["organization_id"],
                user_id=entry["user_id"],
                user_name=entry.get("user_name"),
                date=entry["date"],
                work_location=entry["work_location"],
                project=entry.get("project"),
            )
            for entry in entries
        ]

    async def get_team_week(self, year: int, week: int) -> list[WeeklyPlanRead]:
        if self.auth.permission_scope != "organization":
            raise HTTPException(status_code=403, detail="Organization scope is required for team plans")

        entries = await self.weekly_repo.list_team_by_week(year=year, week=week)
        return [
            WeeklyPlanRead(
                id=entry["id"],
                organization_id=entry["organization_id"],
                user_id=entry["user_id"],
                user_name=entry.get("user_name"),
                date=entry["date"],
                work_location=entry["work_location"],
                project=entry.get("project"),
            )
            for entry in entries
        ]

    async def set_day(
        self,
        target_date: date,
        work_location: PlanLocationValue,
        project: str | None,
    ) -> WeeklyPlanRead:
        try:
            validate_weekday(target_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # Don't commit yet - sync will commit everything at once
        entry = await self.weekly_repo.set_day(
            user_id=self.auth.user.id,
            target_date=target_date,
            work_location=work_location.value,
            project=project,
            commit=False,
        )
        await self._sync_weekly_days_to_monthly(
            [
                {
                    "date": target_date,
                    "work_location": work_location.value,
                    "project": project,
                }
            ],
            commit=True,
        )
        return WeeklyPlanRead.model_validate(entry)

    async def save_week(self, year: int, week: int, body: WeeklyPlanBulkSaveRequest) -> list[WeeklyPlanRead]:
        for day in body.days:
            iso = day.date.isocalendar()
            if iso.year != year or iso.week != week:
                raise HTTPException(status_code=422, detail="All submitted dates must belong to the requested week")

        monday = date.fromisocalendar(year, week, 1)
        friday = date.fromisocalendar(year, week, 5)
        weekly_days = [
            {
                "date": day.date,
                "work_location": day.work_location.value if day.work_location is not None else None,
                "project": day.project,
            }
            for day in body.days
        ]

        # Don't commit yet - sync will commit everything at once
        saved = await self.weekly_repo.replace_range(
            user_id=self.auth.user.id,
            start_date=monday,
            end_date=friday,
            days=weekly_days,
            commit=False,
        )
        # Sync to monthly table and commit everything
        await self._sync_weekly_days_to_monthly(weekly_days, commit=True)
        return [WeeklyPlanRead.model_validate(entry) for entry in saved]

    async def save_month(self, year: int, month: int, body: WeeklyPlanBulkSaveRequest) -> list[WeeklyPlanRead]:
        for day in body.days:
            if day.date.year != year or day.date.month != month:
                raise HTTPException(status_code=422, detail="All submitted dates must belong to the requested month")

        month_days = [
            {
                "date": day.date,
                "work_location": day.work_location.value if day.work_location is not None else None,
                "project": day.project,
            }
            for day in body.days
        ]

        # Don't commit yet - sync will commit everything at once
        await self.monthly_repo.replace_range(
            user_id=self.auth.user.id,
            start_date=date(year, month, 1),
            end_date=_month_end(year, month),
            days=month_days,
            commit=False,
        )
        # Sync to weekly table and commit everything
        await self._sync_monthly_days_to_weekly(month_days, commit=True)
        return await self.get_my_month(year=year, month=month)
