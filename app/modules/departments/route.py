from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments.controller import (
    handle_add_member,
    handle_assign_head,
    handle_bulk_assign_members,
    handle_create_department,
    handle_delete_department,
    handle_get_department,
    handle_get_meta,
    handle_get_my_department,
    handle_list_departments,
    handle_remove_head,
    handle_remove_member,
    handle_update_department,
)
from app.modules.departments.schema import (
    BulkMembersRequest,
    DepartmentListResponse,
    DepartmentMetaResponse,
    DepartmentSummary,
    DepartmentUpsertRequest,
    HeadAssignRequest,
    MyDepartmentResponse,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
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


@router.get("/my-head", response_model=list[MyDepartmentResponse])
async def get_my_department(
    access: Annotated[MemberContext, Depends(require_permission("departments", "view", allow_self=True))],
    db: DbSession,
) -> list[MyDepartmentResponse]:
    return await handle_get_my_department(access, db)


@router.get("/{department_id}", response_model=DepartmentSummary)
async def get_department(
    department_id: str,
    access: Annotated[MemberContext, Depends(require_permission("departments", "view", allow_self=True))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_get_department(access, db, department_id)


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


# ── Member management ──────────────────────────────────────────────────────────


@router.post("/{department_id}/members", response_model=DepartmentSummary)
async def add_department_member(
    department_id: str,
    body: HeadAssignRequest,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_add_member(access, db, department_id, body.headMemberId)


@router.post("/{department_id}/members/bulk", response_model=DepartmentSummary)
async def bulk_assign_members(
    department_id: str,
    body: BulkMembersRequest,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_bulk_assign_members(access, db, department_id, body.memberIds)


@router.delete("/{department_id}/members/{member_id}", response_model=DepartmentSummary)
async def remove_department_member(
    department_id: str,
    member_id: str,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_remove_member(access, db, department_id, member_id)


# ── Head management ────────────────────────────────────────────────────────────


@router.post("/{department_id}/heads", response_model=DepartmentSummary)
async def assign_department_head(
    department_id: str,
    body: HeadAssignRequest,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_assign_head(access, db, department_id, body.headMemberId)


@router.delete("/{department_id}/heads/{member_id}", response_model=DepartmentSummary)
async def remove_department_head(
    department_id: str,
    member_id: str,
    access: Annotated[MemberContext, Depends(require_permission("departments", "edit"))],
    db: DbSession,
) -> DepartmentSummary:
    return await handle_remove_head(access, db, department_id, member_id)
