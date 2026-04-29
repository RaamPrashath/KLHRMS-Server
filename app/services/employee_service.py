"""Employee service — business logic layer."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.employee_repository import EmployeeRepository
from app.schemas.auth_context import AuthContext


class EmployeeService:
    def __init__(self, session: AsyncSession, auth: AuthContext) -> None:
        self.repo = EmployeeRepository(session, auth.organization_id)
        self.auth = auth
