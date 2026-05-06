"""
Role controller — orchestrates service calls and returns response schemas.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.role.schema import (
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
)
from app.modules.role.service import (
    create_role,
    delete_role,
    get_role_by_id,
    list_roles,
    update_role,
)
from app.shared.deps.organization_member import MemberContext


async def handle_list_roles(ctx: MemberContext, db: AsyncSession) -> list[RoleResponse]:
    scope = getattr(ctx, "scope", "organization")

    if scope == "self":
        # Member can only see their own role.
        if ctx.member.role is None:
            return []
        return [RoleResponse.model_validate(ctx.member.role)]

    roles = await list_roles(db, ctx.organization.id)
    return [RoleResponse.model_validate(r) for r in roles]


async def handle_create_role(
    ctx: MemberContext,
    db: AsyncSession,
    data: RoleCreateRequest,
) -> RoleResponse:
    role = await create_role(db, ctx.organization.id, data)
    return RoleResponse.model_validate(role)


async def handle_update_role(
    ctx: MemberContext,
    db: AsyncSession,
    role_id: str,
    data: RoleUpdateRequest,
) -> RoleResponse:
    # get_role_by_id is called inside update_role; the 404 is raised there.
    role = await update_role(db, ctx.organization.id, role_id, data)
    return RoleResponse.model_validate(role)


async def handle_delete_role(
    ctx: MemberContext,
    db: AsyncSession,
    role_id: str,
) -> None:
    await delete_role(db, ctx.organization.id, role_id)
