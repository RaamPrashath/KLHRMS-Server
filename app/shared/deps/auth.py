"""
Legacy auth dependency kept in sync with the active Member -> Role model.

Role source of truth:
  Member.roleId -> Role.permissions / Role.name

This module is not the preferred request path for HRMS feature routes
(`organization_member.py` + `permissions.py` handle that), but it should still
resolve membership from the same tables instead of the removed hrmsRole column.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.member import Member
from app.shared.auth_context import AuthContext
from app.shared.database import get_db

logger = logging.getLogger(__name__)

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _normalize_role_name(role_name: str | None) -> str | None:
    if not role_name:
        return None
    return role_name.strip().lower().replace(" ", "_")


def _extract_bearer(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    return auth_header.split(" ", 1)[1].strip()


async def _verify_session_token(token: str, db: AsyncSession) -> dict[str, str]:
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


async def get_auth_context(request: Request, db: DbSession) -> AuthContext:
    token = _extract_bearer(request)
    session_data = await _verify_session_token(token, db)
    user_id = session_data["user_id"]

    org_id_raw = request.headers.get("x-organization-id")
    if not org_id_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="x-organization-id header is required.",
        )

    try:
        organization_id = uuid.UUID(org_id_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid x-organization-id format.",
        ) from exc

    result = await db.execute(
        select(Member)
        .options(joinedload(Member.role))
        .where(
            Member.userId == user_id,
            Member.organizationId == str(organization_id),
        )
    )
    member = result.unique().scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this organization.",
        )

    if member.roleId is None or member.role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member has no organization role assigned.",
        )

    role_name = _normalize_role_name(member.role.name)
    if role_name is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member role is invalid.",
        )

    logger.debug(
        "auth.resolved",
        extra={
            "user_id": user_id,
            "org_id": str(organization_id),
            "role_name": member.role.name,
            "normalized_role": role_name,
        },
    )

    return AuthContext(
        user_id=user_id,
        organization_id=organization_id,
        role=role_name,
        permissions={},
    )


AuthContextDep = Annotated[AuthContext, Depends(get_auth_context)]


def get_organization_id(auth: AuthContextDep) -> uuid.UUID:
    return auth.organization_id


OrganizationIdDep = Annotated[uuid.UUID, Depends(get_organization_id)]


def require_permission(permission: str):
    async def _check(auth: AuthContextDep) -> AuthContext:
        if not auth.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required.",
            )
        return auth

    return _check


def require_roles(*roles: str):
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
