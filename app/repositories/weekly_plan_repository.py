"""Weekly plan data access layer."""
from datetime import date, timedelta

from app.models.weekly_plan import WeeklyPlan
from app.repositories.base import BaseRepository
from app.utils.enums import WorkLocationType


def _iso_week_bounds(year: int, week: int) -> tuple[date, date]:
    """Return (monday, friday) for the given ISO year+week."""
    monday = date.fromisocalendar(year, week, 1)
    friday = monday + timedelta(days=4)
    return monday, friday


class WeeklyPlanRepository(BaseRepository[WeeklyPlan]):
    model = WeeklyPlan

    async def get_by_date(self, user_id: str, target_date: date) -> WeeklyPlan | None:
        """Return the entry for a specific user+date within the org."""
        result = await self.session.execute(
            self._base_query()
            .where(WeeklyPlan.user_id == user_id)
            .where(WeeklyPlan.date == target_date)
        )
        return result.scalar_one_or_none()

    async def list_by_week(
        self, user_id: str, year: int, week: int
    ) -> list[WeeklyPlan]:
        """Return all entries for a user for the given ISO week."""
        monday, friday = _iso_week_bounds(year, week)
        result = await self.session.execute(
            self._base_query()
            .where(WeeklyPlan.user_id == user_id)
            .where(WeeklyPlan.date >= monday)
            .where(WeeklyPlan.date <= friday)
            .order_by(WeeklyPlan.date)
        )
        return list(result.scalars().all())

    async def list_team_by_week(self, year: int, week: int) -> list[WeeklyPlan]:
        """Return all entries for the entire org for the given ISO week."""
        monday, friday = _iso_week_bounds(year, week)
        result = await self.session.execute(
            self._base_query()
            .where(WeeklyPlan.date >= monday)
            .where(WeeklyPlan.date <= friday)
            .order_by(WeeklyPlan.user_id, WeeklyPlan.date)
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        user_id: str,
        target_date: date,
        work_location: WorkLocationType,
        project: str | None,
    ) -> WeeklyPlan:
        """Insert or update the entry for a specific user+date."""
        existing = await self.get_by_date(user_id, target_date)
        if existing is not None:
            existing.work_location = work_location
            existing.project = project
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        return await self.create(
            user_id=user_id,
            date=target_date,
            work_location=work_location,
            project=project,
        )
