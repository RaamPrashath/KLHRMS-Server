from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class AssetMaintenanceLog(Base):
    __tablename__ = "asset_maintenance_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    assetId: Mapped[str] = mapped_column(String(36), ForeignKey("asset.id", ondelete="CASCADE"), nullable=False)
    loggedByMemberId: Mapped[str | None] = mapped_column(String(36), ForeignKey("member.id", ondelete="SET NULL"))
    maintenanceType: Mapped[str] = mapped_column(String(40), nullable=False)
    issueDescription: Mapped[str] = mapped_column(Text, nullable=False)
    serviceDate: Mapped[date] = mapped_column(Date, nullable=False)
    expectedCompletionDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    completedDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="OPEN")
    conditionBeforeMaintenance: Mapped[str | None] = mapped_column(String(40), nullable=True)
    conditionAfterMaintenance: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    asset = relationship("Asset", back_populates="maintenanceLogs")
    loggedByMember = relationship("Member", foreign_keys=[loggedByMemberId])

    __table_args__ = (
        Index("asset_maintenance_log_assetId_idx", "assetId"),
        Index("asset_maintenance_log_status_idx", "status"),
        Index("asset_maintenance_log_serviceDate_idx", "serviceDate"),
    )
