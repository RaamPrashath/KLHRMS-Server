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
"self"         — member can only act on their own resource.

require_permission(module, action, allow_self=False)
  allow_self=True  → accepts both "organization" and "self" scopes.
  allow_self=False → accepts only "organization" scope (default, stricter).
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException

from app.shared.deps.organization_member import MemberContext, get_member_context
from app.shared.utils.permissions import get_member_permission_scope

_SCOPE_ORGANIZATION = "organization"
_SCOPE_SELF = "self"


def require_permission(
    module: str,
    action: str,
    allow_self: bool = False,
) -> Callable[..., MemberContext]:
    """
    Factory that returns a FastAPI dependency enforcing that the resolved
    member has the given module/action permission.

    allow_self=False (default): requires "organization" scope.
    allow_self=True:            accepts "organization" OR "self" scope.

    Raises HTTPException(403) with a generic message for any failure:
      - member has no role
      - module not present in permissions
      - action not present under the module
      - scope is not in the accepted set

    Returns the MemberContext so route handlers can access org/member/role.
    The MemberContext.scope attribute is set to the resolved scope string so
    route handlers can branch on "self" vs "organization" when needed.
    """
    accepted_scopes = {_SCOPE_ORGANIZATION}
    if allow_self:
        accepted_scopes.add(_SCOPE_SELF)

    def _dependency(
        ctx: MemberContext = Depends(get_member_context),
    ) -> MemberContext:
        scope = get_member_permission_scope(ctx.member, module, action)
        if scope not in accepted_scopes:
            raise HTTPException(status_code=403, detail="you dont have permission")
        # Attach the resolved scope so handlers can use it for self-filtering.
        ctx.scope = scope  # type: ignore[attr-defined]
        return ctx

    # Give the inner function a unique name so FastAPI's dependency cache
    # treats each require_permission(module, action) call as distinct.
    _dependency.__name__ = f"require_{module}_{action}_{'self' if allow_self else 'org'}"
    return _dependency
