from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class AssetPurchaseOrder(Base):
    __tablename__ = "asset_purchase_order"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    requisitionId: Mapped[str] = mapped_column(
        String(36), ForeignKey("asset_purchase_requisition.id", ondelete="CASCADE"), nullable=False
    )
    poNumber: Mapped[str] = mapped_column(String(64), nullable=False)
    formatKey: Mapped[str] = mapped_column(String(64), nullable=False, server_default="STANDARD")
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="GENERATED")
    storageBucket: Mapped[str] = mapped_column(String(120), nullable=False)
    storagePath: Mapped[str] = mapped_column(Text, nullable=False)
    fileName: Mapped[str] = mapped_column(String(255), nullable=False)
    recipientMemberId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True
    )
    recipientEmail: Mapped[str] = mapped_column(String(255), nullable=False)
    generatedByMemberId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True
    )
    generatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    templateVersion: Mapped[str] = mapped_column(String(64), nullable=False, server_default="v1")
    templateData: Mapped[dict] = mapped_column(JSON, nullable=False)
    sentAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    emailSubject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emailError: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    requisition = relationship("AssetPurchaseRequisition", back_populates="purchaseOrders")
    recipient = relationship("Member", foreign_keys=[recipientMemberId])
    generatedBy = relationship("Member", foreign_keys=[generatedByMemberId])

    __table_args__ = (
        UniqueConstraint("organizationId", "poNumber", name="apo_org_po_number_key"),
        Index("apo_org_req_idx", "organizationId", "requisitionId"),
        Index("apo_org_status_idx", "organizationId", "status"),
        Index("apo_org_recipient_idx", "organizationId", "recipientMemberId"),
    )
