from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid


class AssetIdDefinition(Base):
    __tablename__ = "asset_id_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(
        String, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assetIdName: Mapped[str] = mapped_column(String(120), nullable=False)
    isActive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
