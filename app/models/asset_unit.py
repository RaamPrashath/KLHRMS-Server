from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class AssetUnit(Base):
    __tablename__ = "asset_unit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    assetId: Mapped[str] = mapped_column(String(36), ForeignKey("asset.id", ondelete="CASCADE"), nullable=False)
    serialNumber: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="AVAILABLE")
    currentHolderMemberId: Mapped[str | None] = mapped_column(String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(40), nullable=True)
    warrantyExpiryDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    lastWarrantyAlertSentAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminderCompleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    asset = relationship("Asset", back_populates="units")

    __table_args__ = (
        Index("asset_unit_asset_idx", "assetId"),
        Index("asset_unit_status_idx", "status"),
        Index("asset_unit_holder_idx", "currentHolderMemberId"),
        Index("asset_unit_warranty_expiry_idx", "warrantyExpiryDate"),
    )
