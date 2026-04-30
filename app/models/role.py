from sqlalchemy import ForeignKey, String, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Role(Base, TimestampMixin):
    __tablename__ = "Role"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)

    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("Organization.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organizationId", "id",
            name="Role_organizationId_id_key"
        ),
        UniqueConstraint(
            "organizationId", "name",
            name="Role_organizationId_name_key"
        ),
        Index(
            "Role_organizationId_idx",
            "organizationId"
        ),
    )