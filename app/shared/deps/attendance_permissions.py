"""
Attendance-specific permission dependency factory.

Builds on get_member_context and get_member_permission_scope to produce
an AttendanceAccessContext that includes the resolved permission scope.

Supported scopes for attendance in this codebase:
  - "self"         → actor may only access their own attendance records
  - "department"   → actor may access records of members in their department
  - "organization" → actor may access any member's records within the org

Usage:

    @router.post("/attendance/clock-in")
    def clock_in(
        access: Annotated[AttendanceAccessContext, Depends(require_attendance_permission("create"))],
        ...
    ):
        ...
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException

from app.models.member import Member
from app.models.organization import Organization
from app.models.role import Role
from app.shared.deps.organization_member import MemberContext, get_member_context
from app.shared.utils.permissions import get_member_permission_scope

# Scopes that can be safely enforced given the current schema.
_SUPPORTED_SCOPES: frozenset[str] = frozenset({"self", "department", "organization"})

# Scopes that exist in the permission contract but cannot be enforced
# because the schema has no team/department tables.
_UNSUPPORTED_SCOPES: frozenset[str] = frozenset({"team"})


@dataclass
class AttendanceAccessContext:
    """
    Enriched context returned to attendance route handlers.

    Fields:
        organization      – resolved Organization ORM instance
        member            – resolved Member ORM instance (the actor)
        role              – resolved Role ORM instance
        permission_action – the attendance action being performed (view/create/edit/delete)
        permission_scope  – the resolved scope ("self", "department", or "organization")
    """

    organization: Organization
    member: Member
    role: Role
    permission_module: str
    permission_action: str
    permission_scope: str


def require_attendance_permission(
    action: str,
    module: str = "attendance",
) -> Callable[..., AttendanceAccessContext]:
    """
    Factory that returns a FastAPI dependency enforcing that the resolved
    member has the attendance.<action> permission at a supported scope.

    Raises:
        HTTPException(403): no attendance permission for the action,
                            scope is unsupported (team/department),
                            or scope is missing/invalid.

    Returns:
        AttendanceAccessContext with the resolved scope included.
    """

    def _dependency(
        ctx: MemberContext = Depends(get_member_context),
    ) -> AttendanceAccessContext:
        scope = get_member_permission_scope(ctx.member, module, action)

        if scope is None or scope == "none":
            raise HTTPException(
                status_code=403,
                detail=f"No {module}.{action} permission",
            )

        if scope in _UNSUPPORTED_SCOPES:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"{module}.{action} scope '{scope}' is not supported in this deployment. "
                    "Only 'self', 'department', and 'organization' scopes are available."
                ),
            )

        if scope not in _SUPPORTED_SCOPES:
            raise HTTPException(
                status_code=403,
                detail=f"Unknown {module}.{action} scope '{scope}'",
            )

        return AttendanceAccessContext(
            organization=ctx.organization,
            member=ctx.member,
            role=ctx.role,
            permission_module=module,
            permission_action=action,
            permission_scope=scope,
        )

    _dependency.__name__ = f"require_{module}_{action}"
    return _dependency
