from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments.controller import (
    handle_assign_team_member,
    handle_create_department,
    handle_create_team,
    handle_delete_department,
    handle_delete_team,
    handle_get_meta,
    handle_list_departments,
    handle_remove_team_member,
    handle_update_department,
    handle_update_team,
)
from app.modules.departments.schema import (
    DepartmentListResponse,
    DepartmentMetaResponse,
    DepartmentSummary,
    DepartmentUpsertRequest,
    TeamMemberAssignRequest,
    TeamSummary,
    TeamUpsertRequest,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/departments", tags=["departments"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=DepartmentListResponse)
async def list_departments(
    access: Annotated[MemberContext, Depends(require_permission("departments", "view", allow_self=True))],
    db: DbSession,
    search: str | None = Query(default=None),
) -> DepartmentListResponse:
    return await handle_list_departments(access, db, search)


@router.get("/meta", response_model=DepartmentMetaResponse)
async def get_department_meta(
    access: Annotated[MemberContext, Depends(require_permission("departments", "view", allow_self=True))],
    db: DbSession,
) -> DepartmentMetaResponse:
    return await handle_get_meta(access, db)


@router.post("", response_model=DepartmentSummary, status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentUpsertRequest,
    access: Annotated[MemberContext, Depends(require_permission("departments", "create"))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_create_department(access, db, body)


@router.patch("/{department_id}", response_model=DepartmentSummary)
async def update_department(
    department_id: str,
    body: DepartmentUpsertRequest,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_update_department(access, db, department_id, body)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: str,
    access: Annotated[MemberContext, Depends(require_permission("departments", "delete"))],
    db: DbSession,
) -> Response:
    await handle_delete_department(access, db, department_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{department_id}/teams", response_model=DepartmentSummary, status_code=status.HTTP_201_CREATED)
async def create_team(
    department_id: str,
    body: TeamUpsertRequest,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_create_team(access, db, department_id, body)


@router.patch("/{department_id}/teams/{team_id}", response_model=DepartmentSummary)
async def update_team(
    department_id: str,
    team_id: str,
    body: TeamUpsertRequest,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_update_team(access, db, department_id, team_id, body)


@router.delete("/{department_id}/teams/{team_id}", response_model=DepartmentSummary)
async def delete_team(
    department_id: str,
    team_id: str,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_delete_team(access, db, department_id, team_id)


@router.post("/teams/{team_id}/members", response_model=TeamSummary)
async def assign_team_member(
    team_id: str,
    body: TeamMemberAssignRequest,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> TeamSummary:
    return await handle_assign_team_member(access, db, team_id, body)


@router.delete("/teams/{team_id}/members/{member_id}", response_model=TeamSummary)
async def remove_team_member(
    team_id: str,
    member_id: str,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> TeamSummary:
    return await handle_remove_team_member(access, db, team_id, member_id)
