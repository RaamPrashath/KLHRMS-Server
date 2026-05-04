"""
FastAPI dependency injection — auth context, RBAC guards, DB session, tenant.

Import from here in all endpoint files:

    from app.shared.deps.auth import AuthContextDep, DbSession, require_roles
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hrms_role import HRMSRole
from app.shared.auth_context import AuthContext
from app.shared.config import get_settings
from app.shared.constants import ROLE_SUPER_ADMIN
from app.shared.database import get_db

logger = logging.getLogger(__name__)
settings = get_settings()

# ── DB session shorthand ──────────────────────────────────────────────────────

DbSession = Annotated[AsyncSession, Depends(get_db)]

# ── Internal helpers ──────────────────────────────────────────────────────────


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    return auth.split(" ", 1)[1].strip()


async def _verify_session_token(token: str, db: AsyncSession) -> dict:
    """
    Verify the Better Auth session token by querying the shared PostgreSQL DB
    directly. Both Next.js (Prisma) and FastAPI (SQLAlchemy) share the same
    Neon database, so we can read the 'session' table without an HTTP round-trip.

    The 'session' table stores the raw token string (not hashed), so a direct
    equality lookup is all that's needed.
    """
    result = await db.execute(
        text(
            """
            SELECT s."userId", s."expiresAt", u.id AS user_id
            FROM session s
            JOIN "user" u ON u.id = s."userId"
            WHERE s.token = :token
            LIMIT 1
            """
        ),
        {"token": token},
    )
    row = result.mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found.",
        )

    expires_at: datetime = row["expiresAt"]
    # Make timezone-aware for comparison if it isn't already
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired.",
        )

    return {"user_id": str(row["user_id"])}


# ── Auth dependency ───────────────────────────────────────────────────────────


async def get_auth_context(request: Request, db: DbSession) -> AuthContext:
    token = _extract_bearer(request)
    session_data = await _verify_session_token(token, db)

    user_id: str = session_data["user_id"]

    # The org ID comes from the x-organization-id header sent by the frontend.
    # This is safe because we verify the user has an active HRMS role in that
    # org in the next step — a user cannot spoof access to another org.
    org_id_raw: str | None = request.headers.get("x-organization-id")

    if not org_id_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="x-organization-id header is required.",
        )

    try:
        organization_id = uuid.UUID(org_id_raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid x-organization-id format.",
        )

    result = await db.execute(
        select(HRMSRole).where(
            HRMSRole.user_id == user_id,
            HRMSRole.organization_id == organization_id,
            HRMSRole.is_active.is_(True),
        )
    )
    hrms_role = result.scalar_one_or_none()

    if hrms_role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active HRMS role found for this user in this organization.",
        )

    return AuthContext(
        user_id=user_id,
        organization_id=organization_id,
        role=hrms_role.role,
        permissions=hrms_role.permissions or {},
    )


AuthContextDep = Annotated[AuthContext, Depends(get_auth_context)]

# ── Tenant shorthand ──────────────────────────────────────────────────────────


def get_organization_id(auth: AuthContextDep) -> uuid.UUID:
    return auth.organization_id


OrganizationIdDep = Annotated[uuid.UUID, Depends(get_organization_id)]

# ── RBAC guards ───────────────────────────────────────────────────────────────


def require_permission(permission: str):
    """
    Dependency factory — raises 403 if the permission flag is not set.
    Usage: dependencies=[Depends(require_permission("payroll:write"))]
    """

    async def _check(auth: AuthContextDep) -> AuthContext:
        if auth.role == ROLE_SUPER_ADMIN:
            return auth
        if not auth.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required.",
            )
        return auth

    return _check


def require_roles(*roles: str):
    """
    Dependency factory — raises 403 if the user's role is not in the allowed list.
    Usage: dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR))]
    """

    async def _check(auth: AuthContextDep) -> AuthContext:
        if auth.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles {list(roles)} required. Current role: {auth.role}.",
            )
        return auth

    return _check
