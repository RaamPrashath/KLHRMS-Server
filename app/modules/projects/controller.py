from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.projects.schema import (
    ProjectDetailResponse,
    ProjectFilters,
    ProjectListResponse,
    ProjectMemberAssignBulkRequest,
    ProjectMemberAssignRequest,
    ProjectMetaResponse,
    ProjectTaskCreateRequest,
    ProjectTaskSummary,
    ProjectUpsertRequest,
)
from app.modules.projects.service import (
    add_project_member,
    bulk_assign_project_members,
    create_project_task,
    delete_project,
    get_project,
    get_project_meta,
    list_project_tasks,
    list_projects,
    list_projects_for_attendance,
    remove_project_member,
    upsert_project,
)
from app.shared.deps.organization_member import MemberContext


async def handle_list_projects(
    ctx: MemberContext, db: AsyncSession, filters: ProjectFilters
) -> ProjectListResponse:
    return await list_projects(db, ctx, filters)


async def handle_get_project(ctx: MemberContext, db: AsyncSession, project_id: str) -> ProjectDetailResponse:
    return await get_project(db, ctx, project_id)


async def handle_create_project(
    ctx: MemberContext, db: AsyncSession, payload: ProjectUpsertRequest
) -> ProjectDetailResponse:
    return await upsert_project(db, ctx, payload)


async def handle_update_project(
    ctx: MemberContext, db: AsyncSession, project_id: str, payload: ProjectUpsertRequest
) -> ProjectDetailResponse:
    return await upsert_project(db, ctx, payload, project_id=project_id)


async def handle_delete_project(ctx: MemberContext, db: AsyncSession, project_id: str) -> None:
    await delete_project(db, ctx, project_id)


async def handle_assign_member(
    ctx: MemberContext, db: AsyncSession, project_id: str, payload: ProjectMemberAssignRequest
) -> ProjectDetailResponse:
    return await add_project_member(db, ctx, project_id, payload)


async def handle_bulk_assign_members(
    ctx: MemberContext, db: AsyncSession, project_id: str, payload: ProjectMemberAssignBulkRequest
) -> ProjectDetailResponse:
    return await bulk_assign_project_members(db, ctx, project_id, payload)


async def handle_revoke_member(
    ctx: MemberContext, db: AsyncSession, project_id: str, member_id: str
) -> ProjectDetailResponse:
    return await remove_project_member(db, ctx, project_id, member_id)


async def handle_list_tasks(
    ctx: MemberContext, db: AsyncSession, project_id: str
) -> list[ProjectTaskSummary]:
    return await list_project_tasks(db, ctx, project_id)


async def handle_create_task(
    ctx: MemberContext, db: AsyncSession, project_id: str, payload: ProjectTaskCreateRequest
) -> list[ProjectTaskSummary]:
    return await create_project_task(db, ctx, project_id, payload)


async def handle_get_meta(ctx: MemberContext, db: AsyncSession) -> ProjectMetaResponse:
    return await get_project_meta(db, ctx)


async def handle_list_projects_for_attendance(ctx: MemberContext, db: AsyncSession):
    return await list_projects_for_attendance(db, ctx)
