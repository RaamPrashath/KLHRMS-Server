"""Payroll service — business logic layer."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.payroll_repository import PayrollRepository
from app.schemas.auth_context import AuthContext


class PayrollService:
    def __init__(self, session: AsyncSession, auth: AuthContext) -> None:
        self.repo = PayrollRepository(session, auth.organization_id)
        self.auth = auth
