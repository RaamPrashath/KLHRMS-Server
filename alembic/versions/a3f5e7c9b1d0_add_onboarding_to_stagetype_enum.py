"""add ONBOARDING to stagetype enum

Revision ID: a3f5e7c9b1d0
Revises: 396982947285
Create Date: 2026-05-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "a3f5e7c9b1d0"
down_revision = "396982947285"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE stagetype ADD VALUE IF NOT EXISTS 'ONBOARDING'")


def downgrade() -> None:
    pass
