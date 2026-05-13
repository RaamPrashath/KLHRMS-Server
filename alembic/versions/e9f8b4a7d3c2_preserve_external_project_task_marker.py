"""preserve external project-task migration marker

Revision ID: e9f8b4a7d3c2
Revises: 5f4aa7b8a682
Create Date: 2026-05-12 15:25:00.000000

This marker preserves a revision that already exists in the local/shared
database but is missing from this checkout. Keeping it in the graph allows
Alembic to continue upgrading without rewriting existing revision history.
"""

from __future__ import annotations

from typing import Sequence, Union


revision: str = "e9f8b4a7d3c2"
down_revision: Union[str, None] = "5f4aa7b8a682"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
