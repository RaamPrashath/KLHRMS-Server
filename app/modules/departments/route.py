from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments.controller import (
    handle_create_department,
    handle_delete_department,
    handle_get_meta,
    handle_list_departments,
    handle_update_department,
)
from app.modules.departments.schema import (
    DepartmentListResponse,
    DepartmentMetaResponse,
    DepartmentSummary,
    DepartmentUpsertRequest,
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

