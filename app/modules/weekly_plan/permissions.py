"""Weekly plan permission helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload

from app.models.member import Member
from app.models.organization import Organization
from app.models.role import Role
from app.models.session import Session as UserSession
from app.models.user import User
from app.shared.database import get_async_db

SUPPORTED_SCOPES: frozenset[str] = frozenset({"self", "department", "organization"})


def get_permission_scope(role_permissions: dict, module: str, action: str) -> str | None:
    if not isinstance(role_permissions, dict):
        return None

    module_permissions = role_permissions.get(module)
    if not isinstance(module_permissions, dict):
        return None

    scope = module_permissions.get(action)
    if not isinstance(scope, str) or not scope:
        return None

    if scope == "org":
        return "organization"
    return scope


@dataclass
class WeeklyPlanAccessContext:
    organization: Organization
    member: Member
    role: Role
    user: User
    permission_action: str
    permission_scope: str


def require_weekly_plan_permission(action: str) -> Callable[..., WeeklyPlanAccessContext]:
    async def _dependency(
        authorization: str = Header(..., alias="Authorization"),
        x_organization_slug: str = Header(..., alias="x-organization-slug"),
        x_membership_id: str = Header(..., alias="x-membership-id"),
        db: AsyncSession = Depends(get_async_db),
    ) -> WeeklyPlanAccessContext:
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or malformed Authorization header.",
            )

        token = authorization.split(" ", 1)[1].strip()

        # Single JOINed query: Session → User → Member → Organization
        # Replaces 3 separate queries (session lookup, org lookup, member+role+user lookup).
        # expiresAt is TIMESTAMP WITHOUT TIME ZONE in the DB, so use naive UTC.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = await db.execute(
            select(Member)
            .join(Member.organization)                     # INNER JOIN for WHERE
            .join(Member.user)                             # INNER JOIN for WHERE
            .join(UserSession, UserSession.userId == User.id)  # INNER JOIN for WHERE
            .options(
                contains_eager(Member.organization),       # populate from join
                contains_eager(Member.user),               # populate from join
                joinedload(Member.role),                   # LEFT JOIN eager load
            )
            .where(
                UserSession.token == token,
                Member.id == x_membership_id,
                Organization.slug == x_organization_slug,
                UserSession.expiresAt > now,
            )
        )
        member = result.unique().scalar_one_or_none()

        if member is None or member.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found or expired.",
            )

        organization = member.organization
        if organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")

        if member.role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access plans.",
            )

        scope = get_permission_scope(member.role.permissions, "weeklyPlan", action)
        if scope is None or scope == "none":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No weeklyPlan.{action} permission",
            )

        if scope not in SUPPORTED_SCOPES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Weekly plan scope '{scope}' is not supported in this deployment. "
                    "Only 'self' and 'organization' scopes are available."
                ),
            )

        return WeeklyPlanAccessContext(
            organization=organization,
            member=member,
            role=member.role,
            user=member.user,
            permission_action=action,
            permission_scope=scope,
        )

    _dependency.__name__ = f"require_weekly_plan_{action}"
    return _dependency
