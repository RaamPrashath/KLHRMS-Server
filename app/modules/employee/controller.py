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
from app.modules.employee import service
from app.shared.deps.organization_member import MemberContext


async def handle_list_employees(
    ctx: MemberContext,
    db: AsyncSession,
) -> EmployeeListResponse:
    scope = getattr(ctx, "scope", "organization")
    return await service.list_employees(
        organization_id=ctx.organization.id,
        db=db,
        scope=scope,
        actor_member_id=ctx.member.id,
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


async def handle_get_employee_detail(
    ctx: MemberContext,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDetailResponse:
    return await service.get_employee_detail(ctx.organization.id, member_id, db)


async def handle_get_my_employee_profile(
    ctx: MemberContext,
    db: AsyncSession,
) -> EmployeeDetailResponse:
    """Return the calling member's own employee profile (for account settings)."""
    return await service.get_employee_detail(ctx.organization.id, ctx.member.id, db)


async def handle_get_employee_direct_reports(
    ctx: MemberContext,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDirectReportsResponse:
    return await service.get_employee_direct_reports(ctx.organization.id, member_id, db)


async def handle_get_employee_group_memberships(
    ctx: MemberContext,
    member_id: str,
    db: AsyncSession,
) -> EmployeeGroupListResponse:
    return await service.get_employee_group_memberships(ctx.organization.id, member_id, db)


async def handle_get_employee_manager_chain(
    ctx: MemberContext,
    member_id: str,
    db: AsyncSession,
) -> EmployeeManagerChainResponse:
    return await service.get_employee_manager_chain(ctx.organization.id, member_id, db)


async def handle_refresh_employee_from_graph(
    ctx: MemberContext,
    member_id: str,
    db: AsyncSession,
) -> EmployeeRefreshResponse:
    return await service.refresh_employee_from_graph(ctx.organization.id, member_id, db)


async def handle_update_employee_details(
    ctx: MemberContext,
    member_id: str,
    body: UpdateEmployeeDetailsRequest,
    db: AsyncSession,
) -> UpdateEmployeeDetailsResponse:
    return await service.update_employee_details(
        ctx.organization.id, member_id, body, db
    )
