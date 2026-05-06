"""
Employee controller — thin orchestration layer.
Delegates to service functions and returns response DTOs.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.employee.schema import (
    EmployeeListFilters,
    EmployeeListResponse,
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
