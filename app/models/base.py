"""
SQLAlchemy declarative bases.

Two bases exist intentionally:

  Base      — for Prisma-synced tables (string PKs, matches Prisma uuid strings)
              Used by: User, Member, Organization, Role, Session, Account,
                       Verification, AttendanceRecord, AttendanceWorkLog,
                       WorkHourPolicy, Department, DepartmentMember

  HRMSBase  — for pure FastAPI/Alembic domain tables (UUID PKs, tenant-isolated)
              Provides: id, organization_id, created_at, updated_at, deleted_at
              Used by: LeaveTypeConfig, LeaveRequest, LeaveBalance, Holiday,
                       EmployeeReporting, WeeklyPlan
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


# ── Prisma-synced base ────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Base for all tables that are also defined in Prisma schema."""
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


# ── Shared mixins ─────────────────────────────────────────────────────────────

class TimestampMixin:
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class TenantMixin:
    """Adds organization_id for tenant isolation. All queries MUST filter by this."""
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )


# ── HRMS domain base ──────────────────────────────────────────────────────────

class HRMSBase(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """
    Base for all pure HRMS domain models (Alembic-only, not in Prisma schema).
    Provides UUID pk, organization_id, created_at, updated_at, deleted_at.
    """
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )