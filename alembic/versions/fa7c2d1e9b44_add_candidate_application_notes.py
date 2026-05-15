"""add candidate application notes

Revision ID: fa7c2d1e9b44
Revises: f4c5c5b65399
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "fa7c2d1e9b44"
down_revision = "f4c5c5b65399"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_application_note",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("applicationId", sa.String(length=36), nullable=False),
        sa.Column("authorMemberId", sa.String(length=36), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["applicationId"], ["candidate_application.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["authorMemberId"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_application_note_applicationId", "candidate_application_note", ["applicationId"])
    op.create_index("ix_candidate_application_note_authorMemberId", "candidate_application_note", ["authorMemberId"])
    op.create_index("ix_candidate_application_note_organizationId", "candidate_application_note", ["organizationId"])
    op.create_index("ix_candidate_note_org_application", "candidate_application_note", ["organizationId", "applicationId"])
    op.create_index("ix_candidate_note_org_author", "candidate_application_note", ["organizationId", "authorMemberId"])


def downgrade() -> None:
    op.drop_index("ix_candidate_note_org_author", table_name="candidate_application_note")
    op.drop_index("ix_candidate_note_org_application", table_name="candidate_application_note")
    op.drop_index("ix_candidate_application_note_organizationId", table_name="candidate_application_note")
    op.drop_index("ix_candidate_application_note_authorMemberId", table_name="candidate_application_note")
    op.drop_index("ix_candidate_application_note_applicationId", table_name="candidate_application_note")
    op.drop_table("candidate_application_note")
