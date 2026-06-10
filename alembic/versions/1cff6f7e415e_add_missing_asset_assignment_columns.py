"""add_missing_asset_assignment_columns

Revision ID: 1cff6f7e415e
Revises: 37ad479eb5ed
Create Date: 2026-06-10 17:06:00.305194
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1cff6f7e415e'
down_revision: Union[str, None] = '37ad479eb5ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("asset_assignment", sa.Column("receivedByMemberId", sa.String(36), sa.ForeignKey("member.id", ondelete="SET NULL"), nullable=True))
    op.add_column("asset_assignment", sa.Column("returnNotes", sa.Text(), nullable=True))
    op.add_column("asset_assignment", sa.Column("expectedReturnDate", sa.DateTime(timezone=True), nullable=True))
    op.add_column("asset_assignment", sa.Column("returnReminderSent", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index("asset_assignment_expectedReturnDate_idx", "asset_assignment", ["expectedReturnDate"])


def downgrade() -> None:
    op.drop_index("asset_assignment_expectedReturnDate_idx")
    op.drop_column("asset_assignment", "returnReminderSent")
    op.drop_column("asset_assignment", "expectedReturnDate")
    op.drop_column("asset_assignment", "returnNotes")
    op.drop_column("asset_assignment", "receivedByMemberId")
