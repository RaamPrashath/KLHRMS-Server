"""
Role controller — orchestrates service calls and returns response schemas.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

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


def handle_list_roles(ctx: MemberContext, db: Session) -> list[RoleResponse]:
    roles = list_roles(db, ctx.organization.id)
    return [RoleResponse.model_validate(r) for r in roles]


def handle_create_role(
    ctx: MemberContext,
    db: Session,
    data: RoleCreateRequest,
) -> RoleResponse:
    role = create_role(db, ctx.organization.id, data)
    return RoleResponse.model_validate(role)


def handle_update_role(
    ctx: MemberContext,
    db: Session,
    role_id: str,
    data: RoleUpdateRequest,
) -> RoleResponse:
    # get_role_by_id is called inside update_role; the 404 is raised there.
    role = update_role(db, ctx.organization.id, role_id, data)
    return RoleResponse.model_validate(role)


def handle_delete_role(
    ctx: MemberContext,
    db: Session,
    role_id: str,
) -> None:
    delete_role(db, ctx.organization.id, role_id)
