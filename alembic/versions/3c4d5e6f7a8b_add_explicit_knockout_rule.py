"""add explicit knockout rule to job requisitions

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-05-25 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c4d5e6f7a8b"
down_revision: str | Sequence[str] | None = "2b3c4d5e6f7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job_requisition", sa.Column("knockoutRule", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_requisition", "knockoutRule")
