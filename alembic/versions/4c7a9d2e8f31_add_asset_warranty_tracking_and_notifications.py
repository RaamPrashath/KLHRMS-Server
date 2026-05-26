"""add asset warranty tracking and notifications

Revision ID: 4c7a9d2e8f31
Revises: 333100a8dc1a
Create Date: 2026-05-26 18:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "4c7a9d2e8f31"
down_revision: str | None = "333100a8dc1a"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "asset_unit",
        sa.Column("warrantyExpiryDate", sa.Date(), nullable=True),
    )
    op.add_column(
        "asset_unit",
        sa.Column("lastWarrantyAlertSentAt", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "asset_unit",
        sa.Column(
            "reminderCompleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "asset_unit_warranty_expiry_idx",
        "asset_unit",
        ["warrantyExpiryDate"],
        unique=False,
    )

    op.create_table(
        "asset_notification",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("assetId", sa.String(length=36), nullable=False),
        sa.Column("assetUnitId", sa.String(length=36), nullable=True),
        sa.Column("memberId", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assetId"], ["asset.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assetUnitId"], ["asset_unit.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["memberId"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("asset_notification_org_idx", "asset_notification", ["organizationId"], unique=False)
    op.create_index("asset_notification_member_idx", "asset_notification", ["memberId"], unique=False)
    op.create_index("asset_notification_type_idx", "asset_notification", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index("asset_notification_type_idx", table_name="asset_notification")
    op.drop_index("asset_notification_member_idx", table_name="asset_notification")
    op.drop_index("asset_notification_org_idx", table_name="asset_notification")
    op.drop_table("asset_notification")

    op.drop_index("asset_unit_warranty_expiry_idx", table_name="asset_unit")
    op.drop_column("asset_unit", "reminderCompleted")
    op.drop_column("asset_unit", "lastWarrantyAlertSentAt")
    op.drop_column("asset_unit", "warrantyExpiryDate")
