"""add hiring team tables

Revision ID: 6f8b7c2d1a44
Revises: 3f7c4a9e2b11
Create Date: 2026-05-12 12:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f8b7c2d1a44"
down_revision: Union[str, None] = "3f7c4a9e2b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hiring_team",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("jobPostingId", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["jobPostingId"], ["job_posting.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hiring_team_organizationId"), "hiring_team", ["organizationId"], unique=False)
    op.create_index(op.f("ix_hiring_team_jobPostingId"), "hiring_team", ["jobPostingId"], unique=False)
    op.create_index("hiring_team_organizationId_idx", "hiring_team", ["organizationId"], unique=False)
    op.create_index("hiring_team_jobPostingId_idx", "hiring_team", ["jobPostingId"], unique=False)
    op.create_index(
        "hiring_team_organizationId_isActive_idx",
        "hiring_team",
        ["organizationId", "isActive"],
        unique=False,
    )

    op.create_table(
        "hiring_team_member",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("hiringTeamId", sa.String(length=36), nullable=False),
        sa.Column("memberId", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["hiringTeamId"], ["hiring_team.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memberId"], ["member.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hiringTeamId", "memberId", name="uq_hiring_team_member"),
    )
    op.create_index(op.f("ix_hiring_team_member_hiringTeamId"), "hiring_team_member", ["hiringTeamId"], unique=False)
    op.create_index(op.f("ix_hiring_team_member_memberId"), "hiring_team_member", ["memberId"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_hiring_team_member_memberId"), table_name="hiring_team_member")
    op.drop_index(op.f("ix_hiring_team_member_hiringTeamId"), table_name="hiring_team_member")
    op.drop_table("hiring_team_member")

    op.drop_index("hiring_team_organizationId_isActive_idx", table_name="hiring_team")
    op.drop_index("hiring_team_jobPostingId_idx", table_name="hiring_team")
    op.drop_index("hiring_team_organizationId_idx", table_name="hiring_team")
    op.drop_index(op.f("ix_hiring_team_jobPostingId"), table_name="hiring_team")
    op.drop_index(op.f("ix_hiring_team_organizationId"), table_name="hiring_team")
    op.drop_table("hiring_team")
