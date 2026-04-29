"""Attendance service — business logic layer."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.attendance_repository import AttendanceRepository
from app.schemas.auth_context import AuthContext


class AttendanceService:
    def __init__(self, session: AsyncSession, auth: AuthContext) -> None:
        self.repo = AttendanceRepository(session, auth.organization_id)
        self.auth = auth
