"""add asset management

Revision ID: 6f2d4b7c9a11
Revises: 3f7c4a9e2b11
Create Date: 2026-05-11 16:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6f2d4b7c9a11"
down_revision: str | None = "3f7c4a9e2b11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Superseded by 12be30a4e06c_rebuild_asset_table_correct_schema.
    # The asset tables are created there with the correct schema.
    # This migration is a no-op to avoid duplicate table creation.
    pass


def _original_upgrade_superseded() -> None:
    op.create_table(
        "asset",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("assetCode", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("serialNumber", sa.String(length=255), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("purchaseDate", sa.Date(), nullable=True),
        sa.Column("purchaseValue", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("warrantyExpiryDate", sa.Date(), nullable=True),
        sa.Column("condition", sa.String(length=40), nullable=False, server_default="GOOD"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="AVAILABLE"),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deletedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("asset_organizationId_idx", "asset", ["organizationId"], unique=False)
    op.create_index("asset_organizationId_assetCode_idx", "asset", ["organizationId", "assetCode"], unique=False)
    op.create_index("asset_organizationId_status_idx", "asset", ["organizationId", "status"], unique=False)
    op.create_index("asset_organizationId_category_idx", "asset", ["organizationId", "category"], unique=False)
    op.create_index("asset_organizationId_deletedAt_idx", "asset", ["organizationId", "deletedAt"], unique=False)

    op.create_table(
        "asset_assignment",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assetId", sa.String(length=36), nullable=False),
        sa.Column("memberId", sa.String(length=36), nullable=False),
        sa.Column("providedByMemberId", sa.String(length=36), nullable=True),
        sa.Column("providedDate", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expectedReturnDate", sa.Date(), nullable=True),
        sa.Column("conditionWhileProviding", sa.String(length=40), nullable=False),
        sa.Column("provideNotes", sa.Text(), nullable=True),
        sa.Column("returnDate", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returnedCondition", sa.String(length=40), nullable=True),
        sa.Column("receivedByMemberId", sa.String(length=36), nullable=True),
        sa.Column("returnNotes", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assetId"], ["asset.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memberId"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["providedByMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["receivedByMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("asset_assignment_assetId_idx", "asset_assignment", ["assetId"], unique=False)
    op.create_index("asset_assignment_memberId_idx", "asset_assignment", ["memberId"], unique=False)
    op.create_index("asset_assignment_expectedReturnDate_idx", "asset_assignment", ["expectedReturnDate"], unique=False)
    op.create_index("asset_assignment_returnDate_idx", "asset_assignment", ["returnDate"], unique=False)

    op.create_table(
        "asset_maintenance_log",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assetId", sa.String(length=36), nullable=False),
        sa.Column("loggedByMemberId", sa.String(length=36), nullable=True),
        sa.Column("maintenanceType", sa.String(length=40), nullable=False),
        sa.Column("issueDescription", sa.Text(), nullable=False),
        sa.Column("serviceDate", sa.Date(), nullable=False),
        sa.Column("expectedCompletionDate", sa.Date(), nullable=True),
        sa.Column("completedDate", sa.Date(), nullable=True),
        sa.Column("cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="OPEN"),
        sa.Column("conditionBeforeMaintenance", sa.String(length=40), nullable=True),
        sa.Column("conditionAfterMaintenance", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assetId"], ["asset.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loggedByMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("asset_maintenance_log_assetId_idx", "asset_maintenance_log", ["assetId"], unique=False)
    op.create_index("asset_maintenance_log_status_idx", "asset_maintenance_log", ["status"], unique=False)
    op.create_index("asset_maintenance_log_serviceDate_idx", "asset_maintenance_log", ["serviceDate"], unique=False)


def downgrade() -> None:
    op.drop_index("asset_maintenance_log_serviceDate_idx", table_name="asset_maintenance_log")
    op.drop_index("asset_maintenance_log_status_idx", table_name="asset_maintenance_log")
    op.drop_index("asset_maintenance_log_assetId_idx", table_name="asset_maintenance_log")
    op.drop_table("asset_maintenance_log")

    op.drop_index("asset_assignment_returnDate_idx", table_name="asset_assignment")
    op.drop_index("asset_assignment_expectedReturnDate_idx", table_name="asset_assignment")
    op.drop_index("asset_assignment_memberId_idx", table_name="asset_assignment")
    op.drop_index("asset_assignment_assetId_idx", table_name="asset_assignment")
    op.drop_table("asset_assignment")

    op.drop_index("asset_organizationId_deletedAt_idx", table_name="asset")
    op.drop_index("asset_organizationId_category_idx", table_name="asset")
    op.drop_index("asset_organizationId_status_idx", table_name="asset")
    op.drop_index("asset_organizationId_assetCode_idx", table_name="asset")
    op.drop_index("asset_organizationId_idx", table_name="asset")
    op.drop_table("asset")
