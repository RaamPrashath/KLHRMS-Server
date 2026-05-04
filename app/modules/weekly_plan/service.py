"""Weekly plan business logic."""
from datetime import date

from app.modules.weekly_plan.repository import WeeklyPlanRepository
from app.modules.weekly_plan.schema import WeeklyPlanDayCreate, WeeklyPlanRead
from app.shared.auth_context import AuthContext
from app.shared.exceptions import BusinessRuleError
from app.shared.utils.enums import WorkLocationType


class WeeklyPlanService:
    def __init__(self, repo: WeeklyPlanRepository, auth: AuthContext) -> None:
        self.repo = repo
        self.auth = auth

    async def get_my_week(self, year: int, week: int) -> list[WeeklyPlanRead]:
        """Return the current user's plan entries for the given ISO week."""
        entries = await self.repo.list_by_week(
            user_id=self.auth.user_id, year=year, week=week
        )
        return [WeeklyPlanRead.model_validate(e) for e in entries]

    async def set_day(
        self,
        target_date: date,
        work_location: WorkLocationType,
        project: str | None,
    ) -> WeeklyPlanRead:
        """Upsert a day entry for the current user. Rejects weekends."""
        try:
            WeeklyPlanDayCreate.validate_weekday(target_date)
        except ValueError as exc:
            raise BusinessRuleError(str(exc)) from exc

        entry = await self.repo.upsert(
            user_id=self.auth.user_id,
            target_date=target_date,
            work_location=work_location,
            project=project,
        )
        return WeeklyPlanRead.model_validate(entry)

    async def get_team_week(self, year: int, week: int) -> list[WeeklyPlanRead]:
        """Return all org members' plan entries for the given ISO week."""
        entries = await self.repo.list_team_by_week(year=year, week=week)
        result = []
        for entry in entries:
            read = WeeklyPlanRead(
                id=entry["id"],
                organization_id=entry["organization_id"],
                user_id=entry["user_id"],
                user_name=entry.get("user_name"),
                date=entry["date"],
                work_location=entry["work_location"],
                project=entry.get("project"),
            )
            result.append(read)
        return result
