"""
Read-only SQLAlchemy models for Prisma-managed auth tables.

These models are used ONLY for reading — Prisma owns the schema and migrations
for these tables. They are intentionally NOT imported in models/__init__.py so
Alembic never detects or touches them.

Tables reflected here:
  - "user"         — Better Auth users
  - "member"       — org membership + hrmsRole (the single source of truth for roles)
  - "organization" — tenant root
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class _PrismaBase(DeclarativeBase):
    """Separate declarative base so these models never appear in HRMSBase.metadata."""

    pass


class PrismaUser(_PrismaBase):
    """
    Maps to Prisma's 'user' table (Better Auth).
    Read-only — never write to this from FastAPI.
    """

    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(
        "emailVerified", Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime(timezone=True), nullable=False
    )


class PrismaOrganization(_PrismaBase):
    """
    Maps to Prisma's 'Organization' table.
    Read-only — never write to this from FastAPI.
    """

    __tablename__ = "Organization"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False
    )


class PrismaMember(_PrismaBase):
    """
    Maps to Prisma's 'Member' table.

    hrmsRole stores the Prisma HrmsRole enum value as a plain string:
      SUPER_ADMIN | HR | ADMIN | MANAGER | EMPLOYEE

    FastAPI maps these to lowercase constants at auth time:
      super_admin | hr | admin | manager | employee
    """

    __tablename__ = "Member"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        "organizationId", String(255), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        "userId", String(255), nullable=False, index=True
    )
    hrms_role: Mapped[str | None] = mapped_column(
        "hrmsRole", String(50), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("organizationId", "userId", name="Member_organizationId_userId_key"),
    )
