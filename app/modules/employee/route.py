"""
Employee routes — FastAPI router.

All endpoints require:
  x-organization-slug  (resolved to Organization)
  x-membership-id      (resolved to Member + Role)

Permission enforcement: employees.view
  - "organization" scope → can list all employees
  - "self" scope is not applicable for listing; only org-level access is granted

GET /employees          — paginated employee list with search + filters
GET /employees/departments — department options for filter dropdown
GET /employees/roles       — role options for filter dropdown
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import status

from app.modules.employee.controller import (
    handle_deactivate_employee,
    handle_delete_employee,
    handle_list_departments,
    handle_list_employees,
    handle_list_roles,
    handle_preview_employee_delete,
)
from app.modules.employee.schema import (
    EmployeeDeactivateResponse,
    EmployeeDeletePreview,
    EmployeeDeleteResponse,
    EmployeeListFilters,
    EmployeeListResponse,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=EmployeeListResponse)
async def list_employees(
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "view"))],
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by name or email"),
    department_id: Optional[str] = Query(None, description="Filter by department ID"),
    role_id: Optional[str] = Query(None, description="Filter by role ID"),
    attendance_status: Optional[str] = Query(
        None,
        description="Filter by today's attendance: PRESENT | ABSENT | WORK_FROM_HOME | HALF_DAY | NO_RECORD",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
) -> EmployeeListResponse:
    filters = EmployeeListFilters(
        search=search,
        department_id=department_id,
        role_id=role_id,
        attendance_status=attendance_status,
        page=page,
        page_size=page_size,
    )
    return await handle_list_employees(ctx, filters, db)


@router.get("/departments", response_model=list[dict])
async def list_departments(
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "view"))],
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await handle_list_departments(ctx, db)


@router.get("/roles", response_model=list[dict])
async def list_roles(
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "view"))],
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await handle_list_roles(ctx, db)


@router.get("/{member_id}/delete-preview", response_model=EmployeeDeletePreview)
async def preview_employee_delete(
    member_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeDeletePreview:
    return await handle_preview_employee_delete(ctx, member_id, db)


@router.patch("/{member_id}/deactivate", response_model=EmployeeDeactivateResponse)
async def deactivate_employee(
    member_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeDeactivateResponse:
    return await handle_deactivate_employee(ctx, member_id, db)


@router.delete("/{member_id}", response_model=EmployeeDeleteResponse)
async def delete_employee(
    member_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeDeleteResponse:
    return await handle_delete_employee(ctx, member_id, db)
