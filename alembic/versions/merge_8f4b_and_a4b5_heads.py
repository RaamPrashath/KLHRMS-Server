"""merge 8f4b and a4b5 heads

Revision ID: m001_merge_heads
Revises: 8f4b2d1c9a7e, a4b5c6d7e8f0
Create Date: 2026-06-15 17:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "m001_merge_heads"
down_revision: tuple[str, str] = ("8f4b2d1c9a7e", "a4b5c6d7e8f0")
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
