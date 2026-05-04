from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.models.base import Base, generate_uuid


class Member(Base):
    __tablename__ = "member"  # Prisma: @@map("member")

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )

    userId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )

    roleId: Mapped[str | None] = mapped_column(String(32))

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="members")
    role = relationship("Role", back_populates="members", overlaps="organization")

    __table_args__ = (
        UniqueConstraint(
            "organizationId",
            "userId",
            name="member_organizationId_userId_key",
        ),
        ForeignKeyConstraint(
            ["organizationId", "roleId"],
            ["role.organizationId", "role.id"],
        ),
        Index("member_organizationId_idx", "organizationId"),
        Index("member_userId_idx", "userId"),
    )