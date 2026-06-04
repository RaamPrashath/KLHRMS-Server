"""merge attendance and notification heads

Revision ID: d9e8f7a6b5c4
Revises: c4d5e6f7a8b0, c4a0f8e61d11
Create Date: 2026-06-04 16:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "d9e8f7a6b5c4"
down_revision: tuple[str, str] = ("c4d5e6f7a8b0", "c4a0f8e61d11")
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
