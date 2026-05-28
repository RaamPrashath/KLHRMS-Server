from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid


class ProcurementPurchaseOrderTemplate(Base):
    __tablename__ = "procurement_purchase_order_template"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False, server_default="Default Purchase Order")
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="ACTIVE")
    templateVersion: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    templateData: Mapped[dict] = mapped_column(JSON, nullable=False)
    lastEditedByMemberId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True
    )
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("organizationId", name="procurement_po_template_org_key"),
        Index("procurement_po_template_org_status_idx", "organizationId", "status"),
    )
