"""add isRemote column to attendanceRecord

Revision ID: b7d8e9f0a1b2
Revises: a0b1c2d3e4f5
Create Date: 2026-06-02 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7d8e9f0a1b2"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "attendanceRecord",
        sa.Column("isRemote", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("attendanceRecord", "isRemote")
