"""Weekly plan business logic."""
from datetime import date

from app.core.exceptions import BusinessRuleError
from app.repositories.weekly_plan_repository import WeeklyPlanRepository
from app.schemas.auth_context import AuthContext
from app.schemas.weekly_plan import WeeklyPlanDayCreate, WeeklyPlanRead
from app.utils.enums import WorkLocationType


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
        return [WeeklyPlanRead.model_validate(e) for e in entries]
