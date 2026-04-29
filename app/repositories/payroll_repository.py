"""Payroll repository."""
from sqlalchemy import select

from app.models.payroll import Payroll
from app.repositories.base import BaseRepository


class PayrollRepository(BaseRepository[Payroll]):
    model = Payroll

    async def get_by_period(self, month: int, year: int) -> Payroll | None:
        result = await self.session.execute(
            self._base_query().where(
                Payroll.period_month == month,
                Payroll.period_year == year,
            )
        )
        return result.scalar_one_or_none()
