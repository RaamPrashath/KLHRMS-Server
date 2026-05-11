"""preserve external migration marker

Revision ID: f43cf5b85a2b
Revises: 719a71a8fb80, 3f7c4a9e2b11
Create Date: 2026-05-11 13:30:00.000000

This marker preserves a revision that already exists in the shared/local
database. The migration file was not present in this checkout, so keeping the
revision in the graph lets Alembic move forward without rewriting history.
"""
from __future__ import annotations

from typing import Sequence, Union

revision: str = "f43cf5b85a2b"
down_revision: Union[str, tuple[str, str], None] = (
    "719a71a8fb80",
    "3f7c4a9e2b11",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
