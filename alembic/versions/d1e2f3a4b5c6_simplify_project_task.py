"""simplify project_task to name-only string

Revision ID: d1e2f3a4b5c6
Revises: c4e5f6a7b8d9
Create Date: 2026-05-12 18:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c4e5f6a7b8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("project_task"):
        return

    columns = {col["name"] for col in inspector.get_columns("project_task")}

    # Drop indexes that reference columns we are removing
    indexes = {idx["name"] for idx in inspector.get_indexes("project_task")}
    for idx_name in ("project_task_assignedMemberId_idx", "project_task_projectId_status_idx"):
        if idx_name in indexes:
            op.drop_index(idx_name, table_name="project_task")

    # Drop FK constraint on assignedMemberId if present
    fks = inspector.get_foreign_keys("project_task")
    for fk in fks:
        if "assignedMemberId" in fk.get("constrained_columns", []):
            op.drop_constraint(fk["name"], "project_task", type_="foreignkey")

    # Remove columns that are no longer needed
    for col in ("description", "assignedMemberId", "status", "updatedAt"):
        if col in columns:
            op.drop_column("project_task", col)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("project_task"):
        return

    columns = {col["name"] for col in inspector.get_columns("project_task")}

    if "status" not in columns:
        op.add_column(
            "project_task",
            sa.Column("status", sa.String(length=32), server_default="TODO", nullable=False),
        )
    if "updatedAt" not in columns:
        op.add_column(
            "project_task",
            sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
    if "description" not in columns:
        op.add_column("project_task", sa.Column("description", sa.Text(), nullable=True))
    if "assignedMemberId" not in columns:
        op.add_column(
            "project_task",
            sa.Column("assignedMemberId", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "project_task_assignedMemberId_fkey",
            "project_task",
            "member",
            ["assignedMemberId"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("project_task_assignedMemberId_idx", "project_task", ["assignedMemberId"])
        op.create_index("project_task_projectId_status_idx", "project_task", ["projectId", "status"])
