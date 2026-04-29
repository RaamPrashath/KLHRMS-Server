"""
Better Auth token verification dependency.

Flow:
1. Extract Bearer token from Authorization header.
2. Call Better Auth /api/auth/session endpoint to verify the token
   and retrieve userId + organizationId.
3. Load the HRMS role from hrms_roles table.
4. Return AuthContext — injected into every protected endpoint.

FastAPI does NOT issue tokens. It only verifies them.
"""
import logging
import uuid
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, InvalidTokenError, PermissionDeniedError
from app.models.hrms_role import HRMSRole
from app.schemas.auth_context import AuthContext

logger = logging.getLogger(__name__)
settings = get_settings()

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    return auth.split(" ", 1)[1].strip()


async def _verify_better_auth_session(token: str) -> dict:
    """
    Verify the Better Auth session token.
    Returns the session payload: {userId, organizationId, ...}
    """
    url = f"{settings.better_auth_url}/api/auth/session"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError as exc:
        logger.error("better_auth.unreachable", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unreachable.",
        )

    if resp.status_code == 401:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token verification failed.")

    return resp.json()


async def get_auth_context(
    request: Request,
    db: DbSession,
) -> AuthContext:
    token = _extract_bearer(request)
    session_data = await _verify_better_auth_session(token)

    user_id: str | None = session_data.get("userId") or session_data.get("user", {}).get("id")
    org_id_raw: str | None = (
        session_data.get("organizationId")
        or session_data.get("activeOrganizationId")
    )

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="userId missing from session.")
    if not org_id_raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="organizationId missing from session.")

    try:
        organization_id = uuid.UUID(org_id_raw)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid organizationId format.")

    # Load HRMS role
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
