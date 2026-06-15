"""Stub migration for orphaned revision a7b9c1d3e5f7.

This revision was previously applied to the database but its source file
was deleted. This stub allows Alembic to resolve the revision ID so
it can be stamped to the current head.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7b9c1d3e5f7"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
