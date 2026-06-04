from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NotificationFilter = Literal["all", "read", "unread"]
NotificationStatus = Literal["READ", "UNREAD"]


class NotificationRead(BaseModel):
    id: str
    organizationId: str
    memberId: str
    type: str
    category: str
    title: str
    message: str
    status: NotificationStatus
    actionUrl: str | None
    entityType: str | None
    entityId: str | None
    metadata: dict | None
    readAt: datetime | None
    createdAt: datetime
    updatedAt: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int
    unreadCount: int


class NotificationUnreadCountResponse(BaseModel):
    unreadCount: int


class NotificationMarkAllReadResponse(BaseModel):
    updatedCount: int
