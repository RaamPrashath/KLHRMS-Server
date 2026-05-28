from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class AccessControlLog(Base):
    __tablename__ = "access_control_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    employeeMemberId: Mapped[str] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    assetId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("asset.id", ondelete="SET NULL"), nullable=True
    )
    accessPoint: Mapped[str] = mapped_column(String(120), nullable=False)
    entryMethod: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    enteredAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    isActive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization = relationship("Organization")
    employee = relationship("Member")
    asset = relationship("Asset")

    __table_args__ = (
        Index("acl_org_idx", "organizationId"),
        Index("acl_member_idx", "employeeMemberId"),
        Index("acl_point_idx", "accessPoint"),
        Index("acl_entered_at_idx", "enteredAt"),
        Index("acl_status_idx", "status"),
    )
