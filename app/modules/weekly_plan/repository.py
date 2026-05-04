"""Weekly plan data access layer."""
from datetime import date, timedelta

from sqlalchemy import text

from app.models.weekly_plan import WeeklyPlan
from app.shared.lib.base_repository import BaseRepository
from app.shared.utils.enums import WorkLocationType


def _iso_week_bounds(year: int, week: int) -> tuple[date, date]:
    """Return (monday, friday) for the given ISO year+week."""
    monday = date.fromisocalendar(year, week, 1)
    friday = monday + timedelta(days=4)
    return monday, friday


class WeeklyPlanRepository(BaseRepository[WeeklyPlan]):
    model = WeeklyPlan

    async def get_by_date(self, user_id: str, target_date: date) -> WeeklyPlan | None:
        result = await self.session.execute(
            self._base_query()
            .where(WeeklyPlan.user_id == user_id)
            .where(WeeklyPlan.date == target_date)
        )
        return result.scalar_one_or_none()

    async def list_by_week(self, user_id: str, year: int, week: int) -> list[WeeklyPlan]:
        monday, friday = _iso_week_bounds(year, week)
        result = await self.session.execute(
            self._base_query()
            .where(WeeklyPlan.user_id == user_id)
            .where(WeeklyPlan.date >= monday)
            .where(WeeklyPlan.date <= friday)
            .order_by(WeeklyPlan.date)
        )
        return list(result.scalars().all())

    async def list_team_by_week(self, year: int, week: int) -> list[dict]:
        monday, friday = _iso_week_bounds(year, week)
        result = await self.session.execute(
            text(
                """
                SELECT
                    wp.id,
                    wp.organization_id,
                    wp.user_id,
                    u.name AS user_name,
                    wp.date,
                    wp.work_location,
                    wp.project
                FROM weekly_plans wp
                LEFT JOIN "user" u ON u.id = wp.user_id
                WHERE wp.organization_id = :org_id
                  AND wp.date >= :monday
                  AND wp.date <= :friday
                  AND wp.deleted_at IS NULL
                ORDER BY wp.user_id, wp.date
                """
            ),
            {"org_id": self.organization_id, "monday": monday, "friday": friday},
        )
        rows = result.mappings().all()
        return [dict(row) for row in rows]

    async def upsert(
        self,
        user_id: str,
        target_date: date,
        work_location: WorkLocationType,
        project: str | None,
    ) -> WeeklyPlan:
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
