"""add_resume_parser_history

Revision ID: c4d5e6f7a8b0
Revises: b7d8e9f0a1b2
Create Date: 2026-06-03 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c4d5e6f7a8b0"
down_revision: Union[str, None] = "b7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resumeParserHistory",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("memberId", sa.String(length=36), nullable=False),
        sa.Column("originalFilename", sa.String(length=512), nullable=False),
        sa.Column("templateType", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("jsonUrl", sa.String(length=2048), nullable=True),
        sa.Column("docxUrl", sa.String(length=2048), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["memberId"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "resumeParserHistory_org_member_created_idx",
        "resumeParserHistory",
        ["organizationId", "memberId", "createdAt"],
        unique=False,
    )
    op.create_index(
        "resumeParserHistory_org_created_idx",
        "resumeParserHistory",
        ["organizationId", "createdAt"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("resumeParserHistory_org_created_idx", table_name="resumeParserHistory")
    op.drop_index("resumeParserHistory_org_member_created_idx", table_name="resumeParserHistory")
    op.drop_table("resumeParserHistory")

