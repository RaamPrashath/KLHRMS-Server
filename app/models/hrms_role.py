"""
HRMS role assignments — one record per user per organization.

Roles: super_admin | hr | admin | manager | employee
Permissions stored as JSONB for fine-grained RBAC.
"""
import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.lib.base_model import Base, TimestampMixin


class HRMSRole(Base, TimestampMixin):
    __tablename__ = "hrms_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Better Auth user ID (string — no FK across migration-tool boundary)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    # {"employees:read": true, "payroll:write": false, ...}
    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
