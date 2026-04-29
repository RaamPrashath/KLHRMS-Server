"""Employee repository — tenant-scoped queries."""
import uuid

from sqlalchemy import select

from app.models.employee import Employee
from app.repositories.base import BaseRepository


class EmployeeRepository(BaseRepository[Employee]):
    model = Employee

    async def get_by_user_id(self, user_id: str) -> Employee | None:
        result = await self.session.execute(
            self._base_query().where(Employee.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_department(self, department_id: uuid.UUID) -> list[Employee]:
        result = await self.session.execute(
            self._base_query().where(Employee.department_id == department_id)
        )
        return list(result.scalars().all())
