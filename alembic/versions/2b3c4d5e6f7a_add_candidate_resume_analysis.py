"""add candidate resume analysis

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-05-25 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2b3c4d5e6f7a"
down_revision: str | Sequence[str] | None = "1a2b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_resume_analysis",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("applicationId", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("resumeUrl", sa.Text(), nullable=True),
        sa.Column("resumeContentType", sa.String(length=255), nullable=True),
        sa.Column("resumeFileType", sa.String(length=20), nullable=True),
        sa.Column("resumeSizeBytes", sa.Integer(), nullable=True),
        sa.Column("firewallFlags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("removedSuspiciousText", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("isFlaggedForCheating", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("extractedText", sa.Text(), nullable=True),
        sa.Column("sanitizedText", sa.Text(), nullable=True),
        sa.Column("parserWarnings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extractedFacts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("compositeScore", sa.Integer(), nullable=True),
        sa.Column("rawScore", sa.Integer(), nullable=True),
        sa.Column("maxScore", sa.Integer(), nullable=True),
        sa.Column("evaluationStatus", sa.String(length=32), nullable=True),
        sa.Column("failedKnockouts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("scoreBreakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extractionConfidence", sa.Float(), nullable=True),
        sa.Column("analysisVersion", sa.String(length=20), nullable=False, server_default="0.3"),
        sa.Column("attemptCount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lastError", sa.Text(), nullable=True),
        sa.Column("analyzedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["applicationId"], ["candidate_application.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("applicationId"),
        sa.UniqueConstraint("organizationId", "applicationId", name="uq_candidate_resume_analysis_org_application"),
    )
    op.create_index(
        "ix_candidate_resume_analysis_applicationId",
        "candidate_resume_analysis",
        ["applicationId"],
        unique=True,
    )
    op.create_index(
        "ix_candidate_resume_analysis_organizationId",
        "candidate_resume_analysis",
        ["organizationId"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_resume_analysis_org_application",
        "candidate_resume_analysis",
        ["organizationId", "applicationId"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_resume_analysis_org_status",
        "candidate_resume_analysis",
        ["organizationId", "status"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_resume_analysis_status",
        "candidate_resume_analysis",
        ["status"],
        unique=False,
    )
    op.alter_column("candidate_resume_analysis", "status", server_default=None)
    op.alter_column("candidate_resume_analysis", "isFlaggedForCheating", server_default=None)
    op.alter_column("candidate_resume_analysis", "analysisVersion", server_default=None)
    op.alter_column("candidate_resume_analysis", "attemptCount", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_candidate_resume_analysis_status", table_name="candidate_resume_analysis")
    op.drop_index("ix_candidate_resume_analysis_org_status", table_name="candidate_resume_analysis")
    op.drop_index("ix_candidate_resume_analysis_org_application", table_name="candidate_resume_analysis")
    op.drop_index("ix_candidate_resume_analysis_organizationId", table_name="candidate_resume_analysis")
    op.drop_index("ix_candidate_resume_analysis_applicationId", table_name="candidate_resume_analysis")
    op.drop_table("candidate_resume_analysis")
