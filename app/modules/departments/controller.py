from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments import service
from app.modules.departments.schema import (
    DepartmentListResponse,
    DepartmentMetaResponse,
    DepartmentSummary,
    DepartmentUpsertRequest,
    TeamMemberAssignRequest,
    TeamSummary,
    TeamUpsertRequest,
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


async def handle_create_team(
    ctx: MemberContext, db: AsyncSession, department_id: str, payload: TeamUpsertRequest
) -> DepartmentSummary:
    return await service.upsert_team(db, ctx, department_id, payload)


async def handle_update_team(
    ctx: MemberContext, db: AsyncSession, department_id: str, team_id: str, payload: TeamUpsertRequest
) -> DepartmentSummary:
    return await service.upsert_team(db, ctx, department_id, payload, team_id)


async def handle_delete_team(ctx: MemberContext, db: AsyncSession, department_id: str, team_id: str) -> DepartmentSummary:
    return await service.deactivate_team(db, ctx, department_id, team_id)


async def handle_assign_team_member(
    ctx: MemberContext, db: AsyncSession, team_id: str, payload: TeamMemberAssignRequest
) -> TeamSummary:
    return await service.assign_team_member(db, ctx, team_id, payload)


async def handle_remove_team_member(ctx: MemberContext, db: AsyncSession, team_id: str, member_id: str) -> TeamSummary:
    return await service.remove_team_member(db, ctx, team_id, member_id)
