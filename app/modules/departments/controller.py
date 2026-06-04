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


async def handle_get_department(ctx: MemberContext, db: AsyncSession, department_id: str) -> DepartmentSummary:
    return await service.get_department_by_id(db, ctx, department_id)


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


async def handle_add_member(ctx: MemberContext, db: AsyncSession, department_id: str, member_id: str) -> DepartmentSummary:
    return await service.add_department_member(db, ctx, department_id, member_id)


async def handle_bulk_assign_members(ctx: MemberContext, db: AsyncSession, department_id: str, member_ids: list[str]) -> DepartmentSummary:
    return await service.bulk_assign_department_members(db, ctx, department_id, member_ids)


async def handle_remove_member(ctx: MemberContext, db: AsyncSession, department_id: str, target_member_id: str) -> DepartmentSummary:
    return await service.remove_department_member(db, ctx, department_id, target_member_id)


async def handle_assign_head(ctx: MemberContext, db: AsyncSession, department_id: str, head_member_id: str) -> DepartmentSummary:
    return await service.assign_department_head(db, ctx, department_id, head_member_id)


async def handle_remove_head(ctx: MemberContext, db: AsyncSession, department_id: str, head_member_id: str) -> DepartmentSummary:
    return await service.remove_department_head(db, ctx, department_id, head_member_id)
