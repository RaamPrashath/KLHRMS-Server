from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class Asset(Base):
    __tablename__ = "asset"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)
    assetCode: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    categoryDefinitionId: Mapped[str | None] = mapped_column(String(36), nullable=True)
    serialNumber: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    purchaseDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchasePrice: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    warrantyExpiryDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    condition: Mapped[str] = mapped_column(String(40), nullable=False, server_default="GOOD")
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="AVAILABLE")
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deletedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    provisions = relationship("AssetAssignment", back_populates="asset", cascade="all, delete-orphan")
    maintenanceLogs = relationship("AssetMaintenanceLog", back_populates="asset", cascade="all, delete-orphan")
    units = relationship("AssetUnit", back_populates="asset", cascade="all, delete-orphan")
    customFieldValues = relationship("AssetCustomFieldValue", back_populates="asset", cascade="all, delete-orphan")

    __table_args__ = (
        Index("asset_organizationId_idx", "organizationId"),
        Index("asset_organizationId_assetCode_idx", "organizationId", "assetCode"),
        Index("asset_organizationId_status_idx", "organizationId", "status"),
        Index("asset_organizationId_category_idx", "organizationId", "category"),
        Index("asset_organizationId_deletedAt_idx", "organizationId", "deletedAt"),
    )
