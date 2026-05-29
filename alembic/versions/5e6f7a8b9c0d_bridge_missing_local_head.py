"""bridge missing local database head

Revision ID: 5e6f7a8b9c0d
Revises: 3c4d5e6f7a8b
Create Date: 2026-05-27 22:54:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "5e6f7a8b9c0d"
down_revision: str | Sequence[str] | None = "3c4d5e6f7a8b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
