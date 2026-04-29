"""
RBAC permission guards.

Usage in endpoints:
    @router.post("/payroll")
    async def run_payroll(
        _: Annotated[None, Depends(require_permission("payroll:write"))],
        auth: AuthContextDep,
    ): ...

Or role-based:
    @router.delete("/employees/{id}")
    async def delete_employee(
        _: Annotated[None, Depends(require_roles("super_admin", "hr"))],
        auth: AuthContextDep,
    ): ...
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.deps.auth import AuthContextDep
from app.core.constants import ROLE_SUPER_ADMIN
from app.schemas.auth_context import AuthContext


def require_permission(permission: str):
    """Dependency factory — raises 403 if the permission is not granted."""

    async def _check(auth: AuthContextDep) -> AuthContext:
        if auth.role == ROLE_SUPER_ADMIN:
            return auth  # super_admin bypasses all permission checks
        if not auth.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required.",
            )
        return auth

    return Depends(_check)


def require_roles(*roles: str):
    """Dependency factory — raises 403 if the user's role is not in the allowed list."""

    async def _check(auth: AuthContextDep) -> AuthContext:
        if auth.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles {list(roles)} required. Current role: {auth.role}.",
            )
        return auth

    return Depends(_check)
