from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.projects.controller import (
    handle_assign_member,
    handle_bulk_assign_members,
    handle_create_project,
    handle_create_task,
    handle_delete_project,
    handle_get_meta,
    handle_get_project,
    handle_list_projects,
    handle_list_projects_for_attendance,
    handle_list_tasks,
    handle_revoke_member,
    handle_update_project,
)
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
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/projects", tags=["projects"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    access: Annotated[MemberContext, Depends(require_permission("projects", "view", allow_self=True))],
    db: DbSession,
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    billable: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ProjectListResponse:
    filters = ProjectFilters(
        search=search,
        status=status_filter,
        billable=billable,
        page=page,
        page_size=page_size,
    )
    return await handle_list_projects(access, db, filters)


@router.get("/meta", response_model=ProjectMetaResponse)
async def get_project_meta(
    access: Annotated[MemberContext, Depends(require_permission("projects", "view", allow_self=True))],
    db: DbSession,
) -> ProjectMetaResponse:
    return await handle_get_meta(access, db)


@router.get("/for-attendance")
async def list_projects_for_attendance(
    access: Annotated[MemberContext, Depends(require_permission("attendance", "view", allow_self=True))],
    db: DbSession,
):
    """
    Return active projects with their tasks for attendance work log selection.
    Only returns projects that are ACTIVE and not deleted.
    """
    return await handle_list_projects_for_attendance(access, db)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project_detail(
    project_id: str,
    access: Annotated[MemberContext, Depends(require_permission("projects", "view", allow_self=True))],
    db: DbSession,
) -> ProjectDetailResponse:
    return await handle_get_project(access, db, project_id)


@router.post("", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectUpsertRequest,
    access: Annotated[MemberContext, Depends(require_permission("projects", "create"))],
    db: DbSession,
) -> ProjectDetailResponse:
    return await handle_create_project(access, db, body)


@router.patch("/{project_id}", response_model=ProjectDetailResponse)
async def update_project(
    project_id: str,
    body: ProjectUpsertRequest,
    access: Annotated[MemberContext, Depends(require_permission("projects", "edit"))],
    db: DbSession,
) -> ProjectDetailResponse:
    return await handle_update_project(access, db, project_id, body)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    access: Annotated[MemberContext, Depends(require_permission("projects", "delete"))],
    db: DbSession,
) -> Response:
    await handle_delete_project(access, db, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/members", response_model=ProjectDetailResponse)
async def add_member(
    project_id: str,
    body: ProjectMemberAssignRequest,
    access: Annotated[MemberContext, Depends(require_permission("projects", "edit"))],
    db: DbSession,
) -> ProjectDetailResponse:
    return await handle_assign_member(access, db, project_id, body)


@router.post("/{project_id}/members/bulk", response_model=ProjectDetailResponse)
async def bulk_add_members(
    project_id: str,
    body: ProjectMemberAssignBulkRequest,
    access: Annotated[MemberContext, Depends(require_permission("projects", "edit"))],
    db: DbSession,
) -> ProjectDetailResponse:
    return await handle_bulk_assign_members(access, db, project_id, body)


@router.delete("/{project_id}/members/{member_id}", response_model=ProjectDetailResponse)
async def remove_member(
    project_id: str,
    member_id: str,
    access: Annotated[MemberContext, Depends(require_permission("projects", "edit"))],
    db: DbSession,
) -> ProjectDetailResponse:
    return await handle_revoke_member(access, db, project_id, member_id)


@router.get("/{project_id}/tasks", response_model=list[ProjectTaskSummary])
async def list_tasks(
    project_id: str,
    access: Annotated[MemberContext, Depends(require_permission("projects", "view", allow_self=True))],
    db: DbSession,
) -> list[ProjectTaskSummary]:
    return await handle_list_tasks(access, db, project_id)


@router.post("/{project_id}/tasks", response_model=list[ProjectTaskSummary], status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: str,
    body: ProjectTaskCreateRequest,
    access: Annotated[MemberContext, Depends(require_permission("projects", "edit"))],
    db: DbSession,
) -> list[ProjectTaskSummary]:
    return await handle_create_task(access, db, project_id, body)
