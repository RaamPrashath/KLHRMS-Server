from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments import service
from app.modules.departments.schema import (
    DepartmentListResponse,
    DepartmentMetaResponse,
    DepartmentSummary,
    DepartmentUpsertRequest,
)
from app.shared.deps.organization_member import MemberContext


async def handle_list_departments(ctx: MemberContext, db: AsyncSession, search: str | None) -> DepartmentListResponse:
    return await service.list_departments(db, ctx, search)


async def handle_get_meta(ctx: MemberContext, db: AsyncSession) -> DepartmentMetaResponse:
    return await service.get_department_meta(db, ctx)


async def handle_create_department(ctx: MemberContext, db: AsyncSession, payload: DepartmentUpsertRequest) -> DepartmentSummary:
    return await service.upsert_department(db, ctx, payload)


async def handle_update_department(
    ctx: MemberContext, db: AsyncSession, department_id: str, payload: DepartmentUpsertRequest
) -> DepartmentSummary:
    return await service.upsert_department(db, ctx, payload, department_id)


async def handle_delete_department(ctx: MemberContext, db: AsyncSession, department_id: str) -> None:
    await service.deactivate_department(db, ctx, department_id)

