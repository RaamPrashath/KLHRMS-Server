"""
Generic async repository base.

All domain repositories extend BaseRepository[ModelT].
Every query is automatically scoped to organization_id (zero cross-tenant leakage)
and excludes soft-deleted rows.

Usage:
    class WeeklyPlanRepository(BaseRepository[WeeklyPlan]):
        model = WeeklyPlan
"""
import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.lib.base_model import HRMSBase

ModelT = TypeVar("ModelT", bound=HRMSBase)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    # ── Query foundation ──────────────────────────────────────────────────────

    def _base_query(self):
        """Always start custom queries from here — org-scoped + soft-delete filtered."""
        return select(self.model).where(
            self.model.organization_id == self.organization_id,
            self.model.deleted_at.is_(None),
        )

    # ── Standard CRUD ─────────────────────────────────────────────────────────

    async def get_by_id(self, record_id: uuid.UUID) -> ModelT | None:
        result = await self.session.execute(
            self._base_query().where(self.model.id == record_id)
        )
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 20) -> list[ModelT]:
        result = await self.session.execute(
            self._base_query().offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(self.model).where(
                self.model.organization_id == self.organization_id,
                self.model.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    async def create(self, **kwargs: Any) -> ModelT:
        instance = self.model(organization_id=self.organization_id, **kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, record_id: uuid.UUID) -> bool:
        from datetime import datetime, timezone

        instance = await self.get_by_id(record_id)
        if instance is None:
            return False
        instance.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True
