"""Report service — aggregation queries for reporting module."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth_context import AuthContext


class ReportService:
    def __init__(self, session: AsyncSession, auth: AuthContext) -> None:
        self.session = session
        self.auth = auth
