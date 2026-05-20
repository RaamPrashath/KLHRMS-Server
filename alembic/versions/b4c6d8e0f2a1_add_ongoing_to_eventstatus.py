"""add ONGOING to eventstatus

Revision ID: b4c6d8e0f2a1
Revises: 70353a1155f8
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "b4c6d8e0f2a1"
down_revision = "70353a1155f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE eventstatus ADD VALUE IF NOT EXISTS 'ONGOING'")


def downgrade() -> None:
    # PostgreSQL does not support dropping a single enum value directly.
    pass
