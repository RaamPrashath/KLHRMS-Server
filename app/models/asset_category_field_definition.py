from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class AssetCategoryFieldDefinition(Base):
    __tablename__ = "asset_category_field_definition"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    categoryId: Mapped[str] = mapped_column(String(36), ForeignKey("asset_category_definition.id", ondelete="CASCADE"), nullable=False)
    fieldName: Mapped[str] = mapped_column(String(100), nullable=False)
    fieldType: Mapped[str] = mapped_column(String(20), nullable=False)
    fieldOptions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    isRequired: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    displayOrder: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    category = relationship("AssetCategoryDefinition", back_populates="fields")

    __table_args__ = (
        Index("asset_cat_field_def_cat_idx", "categoryId"),
    )
