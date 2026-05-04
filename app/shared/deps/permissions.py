"""
Permission enforcement dependency factory.

Usage in a route:

    @router.post("/roles")
    def create_role(
        ctx: Annotated[MemberContext, Depends(require_permission("permission", "create"))],
        ...
    ):
        ...
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException

from app.shared.deps.organization_member import MemberContext, get_member_context
from app.shared.utils.permissions import get_member_permission_scope

_REQUIRED_SCOPE = "organization"


def require_permission(module: str, action: str) -> Callable[..., MemberContext]:
    """
    Factory that returns a FastAPI dependency enforcing that the resolved
    member has the given module/action permission at "organization" scope.

    Raises HTTPException(403) with a generic message for any failure:
      - member has no role
      - module not present in permissions
      - action not present under the module
      - scope present but not "organization"

    Returns the MemberContext so route handlers can access org/member/role.
    """

    def _dependency(
        ctx: MemberContext = Depends(get_member_context),
    ) -> MemberContext:
        scope = get_member_permission_scope(ctx.member, module, action)
        if scope != _REQUIRED_SCOPE:
            raise HTTPException(status_code=403, detail="you dont have permission")
        return ctx

    # Give the inner function a unique name so FastAPI's dependency cache
    # treats each require_permission(module, action) call as distinct.
    _dependency.__name__ = f"require_{module}_{action}"
    return _dependency
