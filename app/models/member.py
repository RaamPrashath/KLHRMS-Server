from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Member(Base):
    __tablename__ = "Member"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("Organization.id", ondelete="CASCADE"),
        nullable=False,
    )

    userId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )

    roleId: Mapped[str | None] = mapped_column(String(32), nullable=True)

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "organizationId",
            "userId",
            name="Member_organizationId_userId_key",
        ),
        ForeignKeyConstraint(
            ["organizationId", "roleId"],
            ["Role.organizationId", "Role.id"],
        ),
        Index("Member_organizationId_idx", "organizationId"),
        Index("Member_userId_idx", "userId"),
    )