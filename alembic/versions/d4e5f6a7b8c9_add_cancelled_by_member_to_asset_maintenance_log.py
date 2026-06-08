"""add cancelled by member to asset maintenance log

Revision ID: d4e5f6a7b8c9
Revises: 461e502394e6
Create Date: 2026-06-08 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "461e502394e6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "asset_maintenance_log",
        sa.Column("cancelledByMemberId", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "asset_maintenance_log_cancelledByMemberId_fkey",
        "asset_maintenance_log",
        "member",
        ["cancelledByMemberId"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "asset_maintenance_log_cancelledByMemberId_fkey",
        "asset_maintenance_log",
        type_="foreignkey",
    )
    op.drop_column("asset_maintenance_log", "cancelledByMemberId")