from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class AssetNotification(Base):
    __tablename__ = "asset_notification"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    assetId: Mapped[str] = mapped_column(
        String(36), ForeignKey("asset.id", ondelete="CASCADE"), nullable=False
    )
    assetUnitId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("asset_unit.id", ondelete="SET NULL"), nullable=True
    )
    memberId: Mapped[str] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization = relationship("Organization")
    asset = relationship("Asset")
    assetUnit = relationship("AssetUnit")
    member = relationship("Member")

    __table_args__ = (
        Index("asset_notification_org_idx", "organizationId"),
        Index("asset_notification_member_idx", "memberId"),
        Index("asset_notification_type_idx", "type"),
    )
