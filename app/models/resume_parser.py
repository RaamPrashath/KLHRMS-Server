from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid


class ResumeParserHistory(Base):
    __tablename__ = "resumeParserHistory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )
    memberId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="CASCADE"),
        nullable=False,
    )
    originalFilename: Mapped[str] = mapped_column(String(512), nullable=False)
    templateType: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    messages: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    jsonUrl: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    docxUrl: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("resumeParserHistory_org_member_created_idx", "organizationId", "memberId", "createdAt"),
        Index("resumeParserHistory_org_created_idx", "organizationId", "createdAt"),
    )

