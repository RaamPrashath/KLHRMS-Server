from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def create_notifications(db: AsyncSession, notifications: list[Notification]) -> None:
    if not notifications:
        return
    db.add_all(notifications)
    await db.flush()


async def list_notifications(
    db: AsyncSession,
    organization_id: str,
    member_id: str,
    *,
    status_filter: str,
    limit: int,
    offset: int,
) -> tuple[list[Notification], int]:
    filters = [
        Notification.organizationId == organization_id,
        Notification.memberId == member_id,
    ]
    if status_filter == "read":
        filters.append(Notification.status == "READ")
    elif status_filter == "unread":
        filters.append(Notification.status == "UNREAD")

    count_result = await db.execute(
        select(func.count(Notification.id)).where(*filters)
    )
    total = count_result.scalar_one() or 0

    result = await db.execute(
        select(Notification)
        .where(*filters)
        .order_by(
            Notification.status.asc(),
            Notification.createdAt.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all(), total


async def count_unread_notifications(
    db: AsyncSession,
    organization_id: str,
    member_id: str,
) -> int:
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.organizationId == organization_id,
            Notification.memberId == member_id,
            Notification.status == "UNREAD",
        )
    )
    return result.scalar_one() or 0


async def mark_notification_as_read(
    db: AsyncSession,
    organization_id: str,
    member_id: str,
    notification_id: str,
) -> Notification | None:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.organizationId == organization_id,
            Notification.memberId == member_id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        return None

    if notification.status != "READ":
        notification.status = "READ"
        notification.readAt = datetime.now(UTC)
        await db.flush()
    return notification


async def mark_all_notifications_as_read(
    db: AsyncSession,
    organization_id: str,
    member_id: str,
) -> int:
    now = datetime.now(UTC)
    result = await db.execute(
        update(Notification)
        .where(
            Notification.organizationId == organization_id,
            Notification.memberId == member_id,
            Notification.status == "UNREAD",
        )
        .values(status="READ", readAt=now, updatedAt=now)
    )
    return result.rowcount or 0
