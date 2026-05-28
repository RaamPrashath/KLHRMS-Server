from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class AssetPurchaseRequisition(Base):
    __tablename__ = "asset_purchase_requisition"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    requestType: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="DRAFT")
    requestNumber: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raisedByMemberId: Mapped[str] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    approvedByMemberId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True
    )
    approvedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejectedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewerComment: Mapped[str | None] = mapped_column(Text, nullable=True)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    requiredByDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimatedUnitCost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimatedQuantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimatedTotalCost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    vendorPreference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(24), nullable=True)
    costCenterOrDepartmentId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("department.id", ondelete="SET NULL"), nullable=True
    )
    assetName: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assetCode: Mapped[str | None] = mapped_column(String(120), nullable=True)
    categoryDefinitionId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("asset_category_definition.id", ondelete="SET NULL"), nullable=True
    )
    specificationNotes: Mapped[str | None] = mapped_column(Text, nullable=True)
    maintenanceTicketId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("asset_maintenance_log.id", ondelete="SET NULL"), nullable=True
    )
    assetId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("asset.id", ondelete="SET NULL"), nullable=True
    )
    assetUnitId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("asset_unit.id", ondelete="SET NULL"), nullable=True
    )
    affectedEmployeeId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True
    )
    originalPurchaseDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    warrantyExpiryDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    warrantyStatus: Mapped[str | None] = mapped_column(String(24), nullable=True)
    replacementReason: Mapped[str | None] = mapped_column(Text, nullable=True)
    replacementMode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ticketSnapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    assetSnapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    raisedBy = relationship("Member", foreign_keys=[raisedByMemberId])
    approvedBy = relationship("Member", foreign_keys=[approvedByMemberId])
    affectedEmployee = relationship("Member", foreign_keys=[affectedEmployeeId])
    department = relationship("Department", foreign_keys=[costCenterOrDepartmentId])
    categoryDefinition = relationship("AssetCategoryDefinition", foreign_keys=[categoryDefinitionId])
    maintenanceTicket = relationship("AssetMaintenanceLog", foreign_keys=[maintenanceTicketId])
    asset = relationship("Asset", foreign_keys=[assetId])
    activityLogs = relationship(
        "AssetPurchaseRequisitionActivityLog",
        back_populates="requisition",
        cascade="all, delete-orphan",
        order_by="AssetPurchaseRequisitionActivityLog.createdAt.desc()",
    )
    purchaseOrders = relationship(
        "AssetPurchaseOrder",
        back_populates="requisition",
        cascade="all, delete-orphan",
        order_by="AssetPurchaseOrder.createdAt.desc()",
    )

    __table_args__ = (
        Index("apr_org_status_idx", "organizationId", "status"),
        Index("apr_org_type_idx", "organizationId", "requestType"),
        Index("apr_org_raised_idx", "organizationId", "raisedByMemberId"),
        Index("apr_org_approved_idx", "organizationId", "approvedByMemberId"),
        Index("apr_org_ticket_idx", "organizationId", "maintenanceTicketId"),
    )


class AssetPurchaseRequisitionActivityLog(Base):
    __tablename__ = "asset_purchase_requisition_activity_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    requisitionId: Mapped[str] = mapped_column(
        String(36), ForeignKey("asset_purchase_requisition.id", ondelete="CASCADE"), nullable=False
    )
    actorId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    requisition = relationship("AssetPurchaseRequisition", back_populates="activityLogs")
    actor = relationship("Member", foreign_keys=[actorId])

    __table_args__ = (
        Index("apral_org_requisition_idx", "organizationId", "requisitionId"),
        Index("apral_org_action_idx", "organizationId", "action"),
    )
