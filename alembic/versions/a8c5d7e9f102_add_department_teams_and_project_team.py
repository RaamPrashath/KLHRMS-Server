"""add department teams and project team link

Revision ID: a8c5d7e9f102
Revises: 603a7ce0c013
Create Date: 2026-05-07 18:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8c5d7e9f102"
down_revision: str | tuple[str, str] | None = "603a7ce0c013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "team",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("departmentId", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("leadMemberId", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="ACTIVE", nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["departmentId"], ["department.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leadMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organizationId", "departmentId", "name", name="team_organizationId_departmentId_name_key"),
    )
    op.create_index("team_organizationId_idx", "team", ["organizationId"], unique=False)
    op.create_index("team_departmentId_idx", "team", ["departmentId"], unique=False)
    op.create_index("team_organizationId_status_idx", "team", ["organizationId", "status"], unique=False)
    op.create_index("team_leadMemberId_idx", "team", ["leadMemberId"], unique=False)

    op.create_table(
        "team_member",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("teamId", sa.String(length=36), nullable=False),
        sa.Column("memberId", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=True),
        sa.Column("joinedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["memberId"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teamId"], ["team.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teamId", "memberId", name="team_member_teamId_memberId_key"),
    )
    op.create_index("team_member_teamId_idx", "team_member", ["teamId"], unique=False)
    op.create_index("team_member_memberId_idx", "team_member", ["memberId"], unique=False)

    op.add_column("project", sa.Column("teamId", sa.String(length=36), nullable=True))
    op.create_foreign_key("project_teamId_fkey", "project", "team", ["teamId"], ["id"], ondelete="SET NULL")
    op.create_index("project_teamId_idx", "project", ["teamId"], unique=False)


def downgrade() -> None:
    op.drop_index("project_teamId_idx", table_name="project")
    op.drop_constraint("project_teamId_fkey", "project", type_="foreignkey")
    op.drop_column("project", "teamId")

    op.drop_index("team_member_memberId_idx", table_name="team_member")
    op.drop_index("team_member_teamId_idx", table_name="team_member")
    op.drop_table("team_member")

    op.drop_index("team_leadMemberId_idx", table_name="team")
    op.drop_index("team_organizationId_status_idx", table_name="team")
    op.drop_index("team_departmentId_idx", table_name="team")
    op.drop_index("team_organizationId_idx", table_name="team")
    op.drop_table("team")
