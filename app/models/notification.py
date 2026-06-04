from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    memberId: Mapped[str] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="UNREAD")
    actionUrl: Mapped[str | None] = mapped_column(String(500), nullable=True)
    entityType: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entityId: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadataJson: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    readAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    organization = relationship("Organization")
    member = relationship("Member", back_populates="notifications")

    __table_args__ = (
        Index("notification_org_idx", "organizationId"),
        Index("notification_member_idx", "memberId"),
        Index("notification_status_idx", "status"),
        Index("notification_created_at_idx", "createdAt"),
        Index("notification_org_member_status_idx", "organizationId", "memberId", "status"),
    )
