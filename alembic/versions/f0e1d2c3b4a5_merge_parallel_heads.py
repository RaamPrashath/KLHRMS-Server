"""merge parallel heads

Revision ID: f0e1d2c3b4a5
Revises: 5e6f7a8b9c0d, a1b2c3d4e5f6
Create Date: 2026-05-28 13:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "f0e1d2c3b4a5"
down_revision: tuple[str, str] = ("5e6f7a8b9c0d", "a1b2c3d4e5f6")
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
