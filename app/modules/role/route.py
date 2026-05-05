"""
Role routes — FastAPI router with permission-enforced endpoints.

All endpoints read organization and member context from headers:
  x-organization-slug
  x-membership-id
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.modules.role.controller import (
    handle_create_role,
    handle_delete_role,
    handle_list_roles,
    handle_update_role,
)
from app.modules.role.schema import RoleCreateRequest, RoleResponse, RoleUpdateRequest
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleResponse], status_code=status.HTTP_200_OK)
def list_roles(
    ctx: Annotated[MemberContext, Depends(require_permission("permission", "view", allow_self=True))],
    db: Session = Depends(get_db),
) -> list[RoleResponse]:
    """List roles in the organization.

    - "organization" scope → returns all roles.
    - "self" scope         → returns only the member's own role.
    """
    return handle_list_roles(ctx, db)


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    body: RoleCreateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("permission", "create"))],
    db: Session = Depends(get_db),
) -> RoleResponse:
    """Create a new role in the organization."""
    return handle_create_role(ctx, db, body)


@router.patch(
    "/{role_id}", response_model=RoleResponse, status_code=status.HTTP_200_OK
)
def update_role(
    role_id: str,
    body: RoleUpdateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("permission", "edit"))],
    db: Session = Depends(get_db),
) -> RoleResponse:
    """Partially update a role's name and/or permissions."""
    return handle_update_role(ctx, db, role_id, body)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("permission", "delete"))],
    db: Session = Depends(get_db),
) -> Response:
    """Delete a role from the organization."""
    handle_delete_role(ctx, db, role_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
