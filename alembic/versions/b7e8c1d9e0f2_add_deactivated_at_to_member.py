"""add deactivated_at to member

Revision ID: b7e8c1d9e0f2
Revises: f3a7b8c9d0e1
Create Date: 2026-06-18 00:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b7e8c1d9e0f2"
down_revision: str | None = "f3a7b8c9d0e1"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "member",
        sa.Column("deactivatedAt", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("member", "deactivatedAt")
