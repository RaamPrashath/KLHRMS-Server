"""
FastAPI dependency that resolves Organization and Member context from
trusted request headers:

  x-organization-slug  →  Organization.slug
  x-membership-id      →  Member.id

The dependency validates that the member belongs to the resolved
organization and that the member has a role assigned.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.member import Member
from app.models.organization import Organization
from app.models.role import Role
from app.shared.database import get_db
from app.shared.logging_config import set_user_id


@dataclass
class MemberContext:
    """Resolved context returned to route handlers and downstream deps."""

    organization: Organization
    member: Member
    role: Role


async def get_member_context(
    x_organization_slug: str = Header(..., alias="x-organization-slug"),
    x_membership_id: str = Header(..., alias="x-membership-id"),
    db: AsyncSession = Depends(get_db),
) -> MemberContext:
    """
    Resolve and validate organization + member context from headers.

    Raises:
        HTTPException(404): organization or member not found.
        HTTPException(403): member does not belong to the organization,
                            or member has no role assigned.
    """
    # 1. Load organization by slug
    organization_result = await db.execute(
        select(Organization).where(Organization.slug == x_organization_slug)
    )
    organization: Organization | None = organization_result.scalar_one_or_none()
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    # 2. Load member by id, scoped to the resolved organization
    member_result = await db.execute(
        select(Member)
        .options(joinedload(Member.role))
        .where(
            Member.id == x_membership_id,
            Member.organizationId == organization.id,
        )
    )
    member: Member | None = member_result.unique().scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    # 3. Ensure the member has a role (required for permission checks)
    if member.roleId is None or member.role is None:
        raise HTTPException(status_code=403, detail="you dont have permission")

    role: Role = member.role

    set_user_id(member.userId)

    return MemberContext(organization=organization, member=member, role=role)
