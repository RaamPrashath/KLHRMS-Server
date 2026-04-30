from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ✅ Base MUST come first
class Base(DeclarativeBase):
    pass


class TimestampMixin:
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deletedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


class TenantMixin:
    organizationId: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )


# ✅ This comes AFTER Base is defined
class HRMSBase(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )