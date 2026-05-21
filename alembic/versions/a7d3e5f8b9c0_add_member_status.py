"""add member status column

Revision ID: a7d3e5f8b9c0
Revises: fa7c2d1e9b44
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a7d3e5f8b9c0"
down_revision = "fa7c2d1e9b44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "member",
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("member", "status")
