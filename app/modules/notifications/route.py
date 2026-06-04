from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.schema import (
    NotificationFilter,
    NotificationListResponse,
    NotificationMarkAllReadResponse,
    NotificationRead,
    NotificationUnreadCountResponse,
)
from app.modules.notifications.service import (
    get_member_unread_count,
    list_member_notifications,
    mark_all_member_notifications_as_read,
    mark_member_notification_as_read,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context

router = APIRouter(prefix="/notifications", tags=["notifications"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
MemberAccess = Annotated[MemberContext, Depends(get_member_context)]


@router.get("", response_model=NotificationListResponse)
async def list_notifications_route(
    access: MemberAccess,
    db: DbSession,
    status: NotificationFilter = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> NotificationListResponse:
    return await list_member_notifications(
        db,
        access,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
async def unread_count_route(
    access: MemberAccess,
    db: DbSession,
) -> NotificationUnreadCountResponse:
    unread_count = await get_member_unread_count(db, access)
    return NotificationUnreadCountResponse(unreadCount=unread_count)


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_as_read_route(
    notification_id: str,
    access: MemberAccess,
    db: DbSession,
) -> NotificationRead:
    return await mark_member_notification_as_read(db, access, notification_id)


@router.post("/read-all", response_model=NotificationMarkAllReadResponse)
async def mark_all_notifications_as_read_route(
    access: MemberAccess,
    db: DbSession,
) -> NotificationMarkAllReadResponse:
    updated_count = await mark_all_member_notifications_as_read(db, access)
    return NotificationMarkAllReadResponse(updatedCount=updated_count)
