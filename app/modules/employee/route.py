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
GET /employees/{member_id} — full detail (Microsoft Entra enriched)
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import status

from app.modules.employee.controller import (
    handle_deactivate_employee,
    handle_delete_employee,
    handle_get_employee_detail,
    handle_get_employee_direct_reports,
    handle_get_employee_group_memberships,
    handle_get_employee_manager_chain,
    handle_get_my_employee_profile,
    handle_list_departments,
    handle_list_employees,
    handle_list_roles,
    handle_preview_employee_delete,
    handle_refresh_employee_from_graph,
    handle_update_employee_details,
    handle_update_employee_role,
)
from app.modules.employee.schema import (
    EmployeeDeactivateResponse,
    EmployeeDeletePreview,
    EmployeeDeleteResponse,
    EmployeeDetailResponse,
    EmployeeDirectReportsResponse,
    EmployeeGroupListResponse,
    EmployeeListFilters,
    EmployeeListResponse,
    EmployeeManagerChainResponse,
    EmployeeRefreshResponse,
    UpdateEmployeeDetailsRequest,
    UpdateEmployeeDetailsResponse,
    UpdateEmployeeRoleRequest,
    UpdateEmployeeRoleResponse,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=EmployeeListResponse)
async def list_employees(
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "view"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeListResponse:
    return await handle_list_employees(ctx, db)


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


@router.patch("/{member_id}/role", response_model=UpdateEmployeeRoleResponse)
async def update_employee_role(
    member_id: str,
    body: UpdateEmployeeRoleRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> UpdateEmployeeRoleResponse:
    return await handle_update_employee_role(ctx, member_id, body, db)


@router.get("/me", response_model=EmployeeDetailResponse)
async def get_my_employee_profile(
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "view"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeDetailResponse:
    """Return the calling member's own employee profile (for account settings)."""
    return await handle_get_my_employee_profile(ctx, db)


@router.get("/{member_id}", response_model=EmployeeDetailResponse)
async def get_employee_detail(
    member_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "view"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeDetailResponse:
    return await handle_get_employee_detail(ctx, member_id, db)


@router.put("/{member_id}", response_model=UpdateEmployeeDetailsResponse)
async def update_employee_details(
    member_id: str,
    body: UpdateEmployeeDetailsRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> UpdateEmployeeDetailsResponse:
    """Update editable employee fields (admin override)."""
    return await handle_update_employee_details(ctx, member_id, body, db)


@router.get(
    "/{member_id}/direct-reports",
    response_model=EmployeeDirectReportsResponse,
)
async def get_employee_direct_reports(
    member_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "view"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeDirectReportsResponse:
    return await handle_get_employee_direct_reports(ctx, member_id, db)


@router.get(
    "/{member_id}/groups",
    response_model=EmployeeGroupListResponse,
)
async def get_employee_groups(
    member_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "view"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeGroupListResponse:
    return await handle_get_employee_group_memberships(ctx, member_id, db)


@router.get(
    "/{member_id}/manager-chain",
    response_model=EmployeeManagerChainResponse,
)
async def get_employee_manager_chain(
    member_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "view"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeManagerChainResponse:
    return await handle_get_employee_manager_chain(ctx, member_id, db)


@router.post(
    "/{member_id}/refresh-from-graph",
    response_model=EmployeeRefreshResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh_employee_from_graph(
    member_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeRefreshResponse:
    return await handle_refresh_employee_from_graph(ctx, member_id, db)


@router.delete("/{member_id}", response_model=EmployeeDeleteResponse)
async def delete_employee(
    member_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("employees", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> EmployeeDeleteResponse:
    return await handle_delete_employee(ctx, member_id, db)
