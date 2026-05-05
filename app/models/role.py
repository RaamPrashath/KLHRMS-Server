from sqlalchemy import ForeignKey, String, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Role(Base, TimestampMixin):
    __tablename__ = "role"  # Prisma: @@map("role")

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False)

    organization = relationship("Organization", back_populates="roles")
    members = relationship("Member", foreign_keys="[Member.roleId]", primaryjoin="Member.roleId == Role.id", back_populates="role", overlaps="organization,members")

    __table_args__ = (
        UniqueConstraint("organizationId", "id"),
        UniqueConstraint("organizationId", "name"),
        Index("role_organizationId_idx", "organizationId"),
    )