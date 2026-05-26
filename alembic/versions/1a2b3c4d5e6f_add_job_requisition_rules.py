"""add job requisition rules

Revision ID: 1a2b3c4d5e6f
Revises: 0b1c2d3e4f5a
Create Date: 2026-05-25 13:25:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1a2b3c4d5e6f"
down_revision: str | Sequence[str] | None = "0b1c2d3e4f5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_requisition_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("requisitionId", sa.String(length=36), nullable=False),
        sa.Column("jobPostingId", sa.String(length=36), nullable=True),
        sa.Column("rulesVersion", sa.String(length=20), nullable=False, server_default="1.0"),
        sa.Column("knockoutRules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scoringWeights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sourceSnapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["jobPostingId"], ["job_posting.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requisitionId"], ["job_requisition.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organizationId", "requisitionId", name="uq_job_requisition_rules_org_requisition"),
        sa.UniqueConstraint("requisitionId"),
    )
    op.create_index(
        "ix_job_requisition_rules_jobPostingId",
        "job_requisition_rules",
        ["jobPostingId"],
        unique=False,
    )
    op.create_index(
        "ix_job_requisition_rules_organizationId",
        "job_requisition_rules",
        ["organizationId"],
        unique=False,
    )
    op.create_index(
        "ix_job_requisition_rules_org_posting",
        "job_requisition_rules",
        ["organizationId", "jobPostingId"],
        unique=False,
    )
    op.create_index(
        "ix_job_requisition_rules_org_requisition",
        "job_requisition_rules",
        ["organizationId", "requisitionId"],
        unique=False,
    )
    op.create_index(
        "ix_job_requisition_rules_requisitionId",
        "job_requisition_rules",
        ["requisitionId"],
        unique=True,
    )
    op.alter_column("job_requisition_rules", "rulesVersion", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_job_requisition_rules_requisitionId", table_name="job_requisition_rules")
    op.drop_index("ix_job_requisition_rules_org_requisition", table_name="job_requisition_rules")
    op.drop_index("ix_job_requisition_rules_org_posting", table_name="job_requisition_rules")
    op.drop_index("ix_job_requisition_rules_organizationId", table_name="job_requisition_rules")
    op.drop_index("ix_job_requisition_rules_jobPostingId", table_name="job_requisition_rules")
    op.drop_table("job_requisition_rules")
