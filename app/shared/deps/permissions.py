"""
Permission enforcement dependency factory.

Usage in a route:

    @router.post("/roles")
    def create_role(
        ctx: Annotated[MemberContext, Depends(require_permission("permission", "create"))],
        ...
    ):
        ...

Scopes
------
"organization" — member can act on any resource in the org.
"department"   — member can act on resources in their department(s).
"team"         — member can act on resources in their team(s).
"self"         — member can only act on their own resource.

require_permission(module, action, allow_self=False)
  allow_self=True  → accepts any non-none scope (self, team, department, organization).
  allow_self=False → accepts only team, department, and organization scopes (not self).
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException

from app.shared.deps.organization_member import MemberContext, get_member_context
from app.shared.utils.permissions import get_member_permission_scope


def _is_valid_scope(scope: str | None) -> bool:
    return scope is not None and scope != "none"


def require_any_permission(
    *requirements: tuple[str, str],
) -> Callable[..., MemberContext]:
    """
    Factory that returns a FastAPI dependency enforcing that the resolved
    member has ANY of the given (module, action) permissions.

    Accepts any non-none scope (self, team, department, organization).
    """
    def _dependency(
        ctx: MemberContext = Depends(get_member_context),
    ) -> MemberContext:
        for module, action in requirements:
            scope = get_member_permission_scope(ctx.member, module, action)
            if _is_valid_scope(scope):
                ctx.scope = scope  # type: ignore[attr-defined]
                return ctx
        raise HTTPException(status_code=403, detail="you dont have permission")

    names = "_".join(f"{m}_{a}" for m, a in requirements)
    _dependency.__name__ = f"require_any_{names}"
    return _dependency


def require_permission(
    module: str,
    action: str,
    allow_self: bool = False,
) -> Callable[..., MemberContext]:
    """
    Factory that returns a FastAPI dependency enforcing that the resolved
    member has the given module/action permission.

    allow_self=False (default): accepts "team", "department", or "organization".
    allow_self=True:            also accepts "self" scope.

    Raises HTTPException(403) if:
      - member has no role
      - module not present in permissions
      - action not present under the module
      - scope is None or "none"
      - scope is "self" and allow_self is False

    Returns the MemberContext so route handlers can access org/member/role.
    The MemberContext.scope attribute is set to the resolved scope string so
    route handlers can branch on scope when needed.
    """

    def _dependency(
        ctx: MemberContext = Depends(get_member_context),
    ) -> MemberContext:
        scope = get_member_permission_scope(ctx.member, module, action)
        if not _is_valid_scope(scope):
            raise HTTPException(status_code=403, detail="you dont have permission")
        if not allow_self and scope == "self":
            raise HTTPException(status_code=403, detail="you dont have permission")
        # Attach the resolved scope so handlers can use it for filtering.
        ctx.scope = scope  # type: ignore[attr-defined]
        return ctx

    # Give the inner function a unique name so FastAPI's dependency cache
    # treats each require_permission(module, action) call as distinct.
    _dependency.__name__ = f"require_{module}_{action}_{'self' if allow_self else 'org'}"
    return _dependency
