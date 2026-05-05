"""
Pure permission helpers — no FastAPI or SQLAlchemy dependencies.
These functions are easily unit-testable in isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.member import Member


def get_permission_scope(
    role_permissions: dict,
    module: str,
    action: str,
) -> str | None:
    """
    Extract the scope string for a given module/action from a role's
    permissions dict.

    Returns the scope string (e.g. "organization") if the path exists
    and the value is a non-empty string, otherwise returns None.

    This function is intentionally free of FastAPI/SQLAlchemy imports
    so it can be tested without any framework overhead.
    """
    if not isinstance(role_permissions, dict):
        return None

    module_perms = role_permissions.get(module)
    if not isinstance(module_perms, dict):
        return None

    scope = module_perms.get(action)
    if not isinstance(scope, str) or not scope:
        return None

    return scope


def get_member_permission_scope(
    member: "Member",
    module: str,
    action: str,
) -> str | None:
    """
    Convenience wrapper that reads permissions from member.role.permissions
    and delegates to get_permission_scope.

    Assumes member.role is already loaded (not None).
    """
    if member.role is None:
        return None
    return get_permission_scope(member.role.permissions, module, action)
