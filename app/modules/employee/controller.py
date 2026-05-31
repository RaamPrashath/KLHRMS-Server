"""
Employee controller — thin orchestration layer.
Delegates to service functions and returns response DTOs.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.employee.schema import (
    EmployeeDeletePreview,
    EmployeeDeleteResponse,
    EmployeeDeactivateResponse,
    EmployeeListFilters,
    EmployeeListResponse,
    UpdateEmployeeRoleRequest,
    UpdateEmployeeRoleResponse,
)
from app.modules.employee import service
from app.shared.deps.organization_member import MemberContext


async def handle_list_employees(
    ctx: MemberContext,
    filters: EmployeeListFilters,
    db: AsyncSession,
) -> EmployeeListResponse:
    return await service.list_employees(
        organization_id=ctx.organization.id,
        filters=filters,
        db=db,
    )


async def handle_list_departments(ctx: MemberContext, db: AsyncSession) -> list[dict]:
    return await service.list_departments_for_org(ctx.organization.id, db)


async def handle_list_roles(ctx: MemberContext, db: AsyncSession) -> list[dict]:
    return await service.list_roles_for_org(ctx.organization.id, db)


async def handle_preview_employee_delete(
    ctx: MemberContext,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDeletePreview:
    return await service.preview_employee_delete(ctx.organization.id, member_id, db)


async def handle_delete_employee(
    ctx: MemberContext,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDeleteResponse:
    return await service.delete_employee(ctx.organization.id, member_id, db)


async def handle_update_employee_role(
    ctx: MemberContext,
    member_id: str,
    body: UpdateEmployeeRoleRequest,
    db: AsyncSession,
) -> UpdateEmployeeRoleResponse:
    return await service.update_employee_role(ctx.organization.id, member_id, body.role_id, db)


async def handle_deactivate_employee(
    ctx: MemberContext,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDeactivateResponse:
    return await service.deactivate_employee(ctx.organization.id, member_id, db)
