"""
FastAPI dependency injection — auth context, RBAC guards, DB session, tenant.

Role source of truth: Prisma's 'Member.hrmsRole' column.
  Prisma stores uppercase values: SUPER_ADMIN | HR | ADMIN | MANAGER | EMPLOYEE
  FastAPI constants are lowercase:  super_admin | hr | admin | manager | employee

The mapping is applied once in get_auth_context() so every downstream consumer
(require_roles, services, repositories) always sees lowercase role strings.

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

from app.models.auth_tables import PrismaMember
from app.shared.auth_context import AuthContext
from app.shared.config import get_settings
from app.shared.constants import ROLE_SUPER_ADMIN
from app.shared.database import get_db

logger = logging.getLogger(__name__)
settings = get_settings()

# ── DB session shorthand ──────────────────────────────────────────────────────

DbSession = Annotated[AsyncSession, Depends(get_db)]

# ── Role mapping — Prisma uppercase → FastAPI lowercase ───────────────────────

_PRISMA_ROLE_MAP: dict[str, str] = {
    "SUPER_ADMIN": "super_admin",
    "HR":          "hr",
    "ADMIN":       "admin",
    "MANAGER":     "manager",
    "EMPLOYEE":    "employee",
}


def _map_prisma_role(prisma_role: str | None) -> str | None:
    """Convert a Prisma HrmsRole enum string to the FastAPI lowercase constant."""
    if prisma_role is None:
        return None
    return _PRISMA_ROLE_MAP.get(prisma_role.upper())


# ── Internal helpers ──────────────────────────────────────────────────────────


def _extract_bearer(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    return auth_header.split(" ", 1)[1].strip()


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
            SELECT s."userId", s."expiresAt"
            FROM session s
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
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired.",
        )

    return {"user_id": str(row["userId"])}


# ── Auth dependency ───────────────────────────────────────────────────────────


async def get_auth_context(request: Request, db: DbSession) -> AuthContext:
    """
    Resolve the caller's identity from the Bearer token + x-organization-id header.

    Steps:
      1. Extract and verify the Better Auth session token → user_id
      2. Parse the x-organization-id header → organization_id (UUID)
      3. Query Prisma's Member table for (userId, organizationId)
      4. Map Member.hrmsRole (uppercase) → FastAPI role constant (lowercase)
      5. Return AuthContext with user_id, organization_id, role, permissions={}
    """
    token = _extract_bearer(request)
    session_data = await _verify_session_token(token, db)
    user_id: str = session_data["user_id"]

    # The org ID comes from the x-organization-id header sent by the frontend.
    # We verify the user is actually a member of that org in step 3 below —
    # a user cannot spoof access to an org they don't belong to.
    org_id_raw: str | None = request.headers.get("x-organization-id")

    if not org_id_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="x-organization-id header is required.",
        )

    # Validate UUID format (org IDs are UUIDs in Prisma)
    try:
        organization_id = uuid.UUID(org_id_raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid x-organization-id format.",
        )

    # Query Prisma's Member table — this is the single source of truth for
    # org membership and role assignment.
    result = await db.execute(
        select(PrismaMember).where(
            PrismaMember.user_id == user_id,
            PrismaMember.organization_id == str(organization_id),
        )
    )
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this organization.",
        )

    # Map Prisma uppercase role → FastAPI lowercase constant
    role = _map_prisma_role(member.hrms_role)

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Member has no HRMS role assigned "
                f"(hrmsRole={member.hrms_role!r}). "
                "Contact your organization administrator."
            ),
        )

    logger.debug(
        "auth.resolved",
        extra={
            "user_id": user_id,
            "org_id": str(organization_id),
            "prisma_role": member.hrms_role,
            "mapped_role": role,
        },
    )

    return AuthContext(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
        permissions={},  # Fine-grained permissions come from role alone for now
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

    Roles are compared case-insensitively. Both sides are already lowercase
    (FastAPI constants + mapped AuthContext.role), but the normalization is kept
    as a safety net.

    Usage: dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR))]
    """

    async def _check(auth: AuthContextDep) -> AuthContext:
        normalized_role = (auth.role or "").lower()
        allowed = [r.lower() for r in roles]
        if normalized_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles {list(roles)} required. Current role: {auth.role}.",
            )
        return auth

    return _check
