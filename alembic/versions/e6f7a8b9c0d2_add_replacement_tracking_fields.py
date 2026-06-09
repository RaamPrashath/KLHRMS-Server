"""add expectedReturnDate and returnReminderSent to asset_assignment

Revision ID: e6f7a8b9c0d2
Revises: d4e5f6a7b8c9
Create Date: 2026-06-08 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d2"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "asset_assignment",
        sa.Column("expectedReturnDate", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "asset_assignment",
        sa.Column(
            "returnReminderSent",
            sa.Boolean,
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "asset_assignment_expectedReturnDate_idx",
        "asset_assignment",
        ["expectedReturnDate"],
    )


def downgrade() -> None:
    op.drop_index("asset_assignment_expectedReturnDate_idx", table_name="asset_assignment")
    op.drop_column("asset_assignment", "returnReminderSent")
    op.drop_column("asset_assignment", "expectedReturnDate")
