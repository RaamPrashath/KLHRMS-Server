from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.modules.notifications import repository
from app.modules.notifications.schema import NotificationListResponse, NotificationRead
from app.shared.deps.organization_member import MemberContext


@dataclass(slots=True)
class NotificationCreateInput:
    organization_id: str
    member_id: str
    type: str
    category: str
    title: str
    message: str
    action_url: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    metadata: dict | None = field(default=None)


def _serialize_notification(notification: Notification) -> NotificationRead:
    return NotificationRead(
        id=notification.id,
        organizationId=notification.organizationId,
        memberId=notification.memberId,
        type=notification.type,
        category=notification.category,
        title=notification.title,
        message=notification.message,
        status=notification.status,
        actionUrl=notification.actionUrl,
        entityType=notification.entityType,
        entityId=notification.entityId,
        metadata=notification.metadataJson,
        readAt=notification.readAt,
        createdAt=notification.createdAt,
        updatedAt=notification.updatedAt,
    )


async def create_notification_batch(
    db: AsyncSession,
    notifications: list[NotificationCreateInput],
) -> None:
    if not notifications:
        return

    rows = [
        Notification(
            organizationId=item.organization_id,
            memberId=item.member_id,
            type=item.type,
            category=item.category,
            title=item.title,
            message=item.message,
            status="UNREAD",
            actionUrl=item.action_url,
            entityType=item.entity_type,
            entityId=item.entity_id,
            metadataJson=item.metadata,
        )
        for item in notifications
    ]
    await repository.create_notifications(db, rows)


async def list_member_notifications(
    db: AsyncSession,
    ctx: MemberContext,
    *,
    status_filter: str,
    limit: int,
    offset: int,
) -> NotificationListResponse:
    items, total = await repository.list_notifications(
        db,
        ctx.organization.id,
        ctx.member.id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    unread_count = await repository.count_unread_notifications(
        db,
        ctx.organization.id,
        ctx.member.id,
    )
    return NotificationListResponse(
        items=[_serialize_notification(item) for item in items],
        total=total,
        unreadCount=unread_count,
    )


async def get_member_unread_count(db: AsyncSession, ctx: MemberContext) -> int:
    return await repository.count_unread_notifications(db, ctx.organization.id, ctx.member.id)


async def mark_member_notification_as_read(
    db: AsyncSession,
    ctx: MemberContext,
    notification_id: str,
) -> NotificationRead:
    notification = await repository.mark_notification_as_read(
        db,
        ctx.organization.id,
        ctx.member.id,
        notification_id,
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return _serialize_notification(notification)


async def mark_all_member_notifications_as_read(
    db: AsyncSession,
    ctx: MemberContext,
) -> int:
    updated_count = await repository.mark_all_notifications_as_read(
        db,
        ctx.organization.id,
        ctx.member.id,
    )
    await db.commit()
    return updated_count
