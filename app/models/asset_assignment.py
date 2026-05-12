from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class AssetAssignment(Base):
    __tablename__ = "asset_assignment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    assetId: Mapped[str] = mapped_column(String(36), ForeignKey("asset.id", ondelete="CASCADE"), nullable=False)
    memberId: Mapped[str] = mapped_column(String(36), ForeignKey("member.id", ondelete="CASCADE"), nullable=False)
    providedByMemberId: Mapped[str | None] = mapped_column(String(36), ForeignKey("member.id", ondelete="SET NULL"))
    providedDate: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    conditionWhileProviding: Mapped[str] = mapped_column(String(40), nullable=False)
    provideNotes: Mapped[str | None] = mapped_column(Text, nullable=True)
    returnDate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    returnedCondition: Mapped[str | None] = mapped_column(String(40), nullable=True)
    receivedByMemberId: Mapped[str | None] = mapped_column(String(36), ForeignKey("member.id", ondelete="SET NULL"))
    returnNotes: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    asset = relationship("Asset", back_populates="provisions")
    member = relationship("Member", foreign_keys=[memberId])
    providedByMember = relationship("Member", foreign_keys=[providedByMemberId])
    receivedByMember = relationship("Member", foreign_keys=[receivedByMemberId])

    __table_args__ = (
        Index("asset_assignment_assetId_idx", "assetId"),
        Index("asset_assignment_memberId_idx", "memberId"),
        Index("asset_assignment_returnDate_idx", "returnDate"),
    )
