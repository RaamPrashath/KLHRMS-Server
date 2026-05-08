"""project module compatibility marker

Revision ID: 603a7ce0c013
Revises: f31c0d9b7a12
Create Date: 2026-05-07 12:37:01.150043
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "603a7ce0c013"
down_revision: str | tuple[str, str] | None = "f31c0d9b7a12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
