"""add clock-in project/task metadata to attendanceRecord

Revision ID: 8b7a8c1d2e3f
Revises: 5f4aa7b8a682
Create Date: 2026-05-12 15:10:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b7a8c1d2e3f"
down_revision: Union[str, None] = "e9f8b4a7d3c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("attendanceRecord"):
        return

    columns = {column["name"] for column in inspector.get_columns("attendanceRecord")}
    indexes = {index["name"] for index in inspector.get_indexes("attendanceRecord")}

    if "projectId" not in columns:
        op.add_column("attendanceRecord", sa.Column("projectId", sa.String(length=36), nullable=True))
    if "projectTaskId" not in columns:
        op.add_column("attendanceRecord", sa.Column("projectTaskId", sa.String(length=36), nullable=True))
    if "description" not in columns:
        op.add_column("attendanceRecord", sa.Column("description", sa.String(length=1000), nullable=True))

    if "attendanceRecord_projectId_idx" not in indexes:
        op.create_index("attendanceRecord_projectId_idx", "attendanceRecord", ["projectId"], unique=False)
    if "attendanceRecord_projectTaskId_idx" not in indexes:
        op.create_index("attendanceRecord_projectTaskId_idx", "attendanceRecord", ["projectTaskId"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("attendanceRecord"):
        return

    columns = {column["name"] for column in inspector.get_columns("attendanceRecord")}
    indexes = {index["name"] for index in inspector.get_indexes("attendanceRecord")}

    if "attendanceRecord_projectTaskId_idx" in indexes:
        op.drop_index("attendanceRecord_projectTaskId_idx", table_name="attendanceRecord")
    if "attendanceRecord_projectId_idx" in indexes:
        op.drop_index("attendanceRecord_projectId_idx", table_name="attendanceRecord")

    if "description" in columns:
        op.drop_column("attendanceRecord", "description")
    if "projectTaskId" in columns:
        op.drop_column("attendanceRecord", "projectTaskId")
    if "projectId" in columns:
        op.drop_column("attendanceRecord", "projectId")
