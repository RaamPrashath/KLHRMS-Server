"""retire broken sync models with db migration

Revision ID: 05aedd93e08d
Revises: d9e8f7a6b5c4
Create Date: 2026-06-01 15:35:52.387838
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "05aedd93e08d"
down_revision: str | None = "d9e8f7a6b5c4"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
