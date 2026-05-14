from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class AssetCustomFieldValue(Base):
    __tablename__ = "asset_custom_field_value"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    assetId: Mapped[str] = mapped_column(String(36), ForeignKey("asset.id", ondelete="CASCADE"), nullable=False)
    fieldDefinitionId: Mapped[str] = mapped_column(String(36), ForeignKey("asset_category_field_definition.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset = relationship("Asset", back_populates="customFieldValues")
    fieldDefinition = relationship("AssetCategoryFieldDefinition")

    __table_args__ = (
        Index("asset_custom_field_asset_idx", "assetId"),
        Index("asset_custom_field_def_idx", "fieldDefinitionId"),
        Index("asset_custom_field_asset_def_idx", "assetId", "fieldDefinitionId", unique=True),
    )
