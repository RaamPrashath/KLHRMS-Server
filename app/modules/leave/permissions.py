"""
Leave-specific permission helpers and dependency factories.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException

from app.models.member import Member
from app.models.organization import Organization
from app.models.role import Role
from app.shared.deps.organization_member import MemberContext, get_member_context

_SUPPORTED_SCOPES: frozenset[str] = frozenset({"self", "organization"})


def get_permission_scope(
    role_permissions: dict,
    module: str,
    action: str,
) -> str | None:
    """Return the normalized scope string for module/action permissions."""
    if not isinstance(role_permissions, dict):
        return None

    module_permissions = role_permissions.get(module)
    if not isinstance(module_permissions, dict):
        return None

    scope = module_permissions.get(action)
    if not isinstance(scope, str) or not scope:
        return None

    if scope == "org":
        return "organization"
    return scope


def has_permission(
    role_permissions: dict,
    module: str,
    action: str,
) -> bool:
    """Return True when a normalized permission scope exists."""
    return get_permission_scope(role_permissions, module, action) is not None


@dataclass
class LeaveAccessContext:
    organization: Organization
    member: Member
    role: Role
    permission_action: str
    permission_scope: str


def require_leave_permission(action: str) -> Callable[..., LeaveAccessContext]:
    """Enforce that the current member has a supported leaves permission."""

    def _dependency(
        ctx: MemberContext = Depends(get_member_context),
    ) -> LeaveAccessContext:
        permissions = ctx.role.permissions if ctx.role is not None else {}
        scope = get_permission_scope(permissions, "leaves", action)

        if scope is None:
            raise HTTPException(
                status_code=403,
                detail=f"No leaves.{action} permission",
            )

        if scope not in _SUPPORTED_SCOPES:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Leave scope '{scope}' is not supported in this deployment. "
                    "Only 'self' and 'organization' scopes are available."
                ),
            )

        return LeaveAccessContext(
            organization=ctx.organization,
            member=ctx.member,
            role=ctx.role,
            permission_action=action,
            permission_scope=scope,
        )

    _dependency.__name__ = f"require_leave_{action}"
    return _dependency
