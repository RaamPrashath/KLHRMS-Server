"""Attendance repository."""
import uuid
from datetime import date

from sqlalchemy import select

from app.models.attendance import Attendance
from app.repositories.base import BaseRepository


class AttendanceRepository(BaseRepository[Attendance]):
    model = Attendance

    async def get_by_employee_and_date(
        self, employee_id: uuid.UUID, record_date: date
    ) -> Attendance | None:
        result = await self.session.execute(
            self._base_query().where(
                Attendance.employee_id == employee_id,
                Attendance.date == record_date,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_employee(
        self, employee_id: uuid.UUID, offset: int = 0, limit: int = 30
    ) -> list[Attendance]:
        result = await self.session.execute(
            self._base_query()
            .where(Attendance.employee_id == employee_id)
            .order_by(Attendance.date.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
