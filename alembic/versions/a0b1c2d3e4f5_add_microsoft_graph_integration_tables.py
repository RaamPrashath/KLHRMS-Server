"""add microsoft graph integration tables

Revision ID: a0b1c2d3e4f5
Revises: 06f743fcc62a
Create Date: 2026-05-29 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "06f743fcc62a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── microsoft_integration_setting ──────────────────────────────────────────
    op.create_table(
        "microsoft_integration_setting",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tenant_id", sa.Text, nullable=False, server_default=""),
        sa.Column("client_id", sa.Text, nullable=False, server_default=""),
        sa.Column("client_secret_ciphertext", sa.Text, nullable=False, server_default=""),
        sa.Column("encryption_iv", sa.String(64), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(20), nullable=True),
        sa.Column("last_sync_summary", JSONB, nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_microsoft_integration_setting_org",
        "microsoft_integration_setting",
        ["organization_id"],
    )

    # ── microsoft_sync_run ─────────────────────────────────────────────────────
    op.create_table(
        "microsoft_sync_run",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("total_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("errors", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by_member_id", sa.String(36), sa.ForeignKey("member.id", ondelete="SET NULL"), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── microsoft_sync_log ─────────────────────────────────────────────────────
    op.create_table(
        "microsoft_sync_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sync_run_id", UUID(as_uuid=True), sa.ForeignKey("microsoft_sync_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.String(10), nullable=False, server_default="info"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_microsoft_sync_log_run",
        "microsoft_sync_log",
        ["sync_run_id"],
    )

    # ── employee ───────────────────────────────────────────────────────────────
    op.create_table(
        "employee",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("member.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("microsoft_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("user_principal_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("employee_id", sa.String(255), nullable=True),
        sa.Column("department_name", sa.String(255), nullable=True),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("mobile_phone", sa.String(50), nullable=True),
        sa.Column("office_location", sa.String(255), nullable=True),
        sa.Column("account_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("profile_photo_url", sa.String(512), nullable=True),
        sa.Column("manager_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="SET NULL"), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_employee_org_microsoft_id", "employee", ["organization_id", "microsoft_id"], unique=True)
    op.create_index("ix_employee_org_email", "employee", ["organization_id", "email"])
    op.create_index("ix_employee_status", "employee", ["organization_id", "status"])

    # ── employee_group ─────────────────────────────────────────────────────────
    op.create_table(
        "employee_group",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("microsoft_group_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("group_type", sa.String(50), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_employee_group_org_ms_id",
        "employee_group",
        ["organization_id", "microsoft_group_id"],
        unique=True,
    )

    # ── employee_group_membership ──────────────────────────────────────────────
    op.create_table(
        "employee_group_membership",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("employee_group.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="CASCADE"), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("group_id", "employee_id", name="uq_group_membership"),
    )


def downgrade() -> None:
    op.drop_table("employee_group_membership")
    op.drop_table("employee_group")
    op.drop_table("employee")
    op.drop_table("microsoft_sync_log")
    op.drop_table("microsoft_sync_run")
    op.drop_table("microsoft_integration_setting")
