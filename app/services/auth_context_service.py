"""
Auth context service.
Resolves and caches HRMS role for a given user+org pair.
Called by the auth dependency on every request.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hrms_role import HRMSRole


async def get_hrms_role(
    session: AsyncSession,
    user_id: str,
    organization_id: uuid.UUID,
) -> HRMSRole | None:
    result = await session.execute(
        select(HRMSRole).where(
            HRMSRole.user_id == user_id,
            HRMSRole.organization_id == organization_id,
            HRMSRole.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()
