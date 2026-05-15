from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class AssetCategoryDefinition(Base):
    __tablename__ = "asset_category_definition"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    assetCode: Mapped[str | None] = mapped_column("asset_code", String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    isActive: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    fields = relationship(
        "AssetCategoryFieldDefinition",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="AssetCategoryFieldDefinition.displayOrder",
    )

    __table_args__ = (
        Index("asset_category_def_org_idx", "organizationId"),
        Index("asset_category_def_org_name_idx", "organizationId", "name"),
    )
