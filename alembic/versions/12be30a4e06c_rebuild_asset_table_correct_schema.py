"""rebuild_asset_table_correct_schema

Revision ID: 12be30a4e06c
Revises: 81fed00139f0
Create Date: 2026-05-11 13:39:57.511181
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "12be30a4e06c"
down_revision: Union[str, None] = "81fed00139f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old asset tables created by 0dab7d02517c (wrong schema — missing assetCode,
    # purchaseValue, warrantyExpiryDate, location; had wrong column names like make/value)
    op.drop_index("asset_maintenance_log_loggedAt_idx", table_name="asset_maintenance_log")
    op.drop_index("asset_maintenance_log_assetId_idx", table_name="asset_maintenance_log")
    op.drop_table("asset_maintenance_log")

    op.drop_index("asset_assignment_expectedReturnDate_idx", table_name="asset_assignment")
    op.drop_index("asset_assignment_memberId_idx", table_name="asset_assignment")
    op.drop_index("asset_assignment_assetId_idx", table_name="asset_assignment")
    op.drop_table("asset_assignment")

    op.drop_index("asset_organizationId_status_idx", table_name="asset")
    op.drop_index("asset_organizationId_deletedAt_idx", table_name="asset")
    op.drop_index("asset_organizationId_category_idx", table_name="asset")
    op.drop_index("asset_organizationId_idx", table_name="asset")
    op.drop_table("asset")

    # Recreate asset with the correct schema
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
    op.create_index("asset_organizationId_idx", "asset", ["organizationId"])
    op.create_index("asset_organizationId_assetCode_idx", "asset", ["organizationId", "assetCode"])
    op.create_index("asset_organizationId_status_idx", "asset", ["organizationId", "status"])
    op.create_index("asset_organizationId_category_idx", "asset", ["organizationId", "category"])
    op.create_index("asset_organizationId_deletedAt_idx", "asset", ["organizationId", "deletedAt"])

    # Recreate asset_assignment with the correct schema
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
    op.create_index("asset_assignment_assetId_idx", "asset_assignment", ["assetId"])
    op.create_index("asset_assignment_memberId_idx", "asset_assignment", ["memberId"])
    op.create_index("asset_assignment_expectedReturnDate_idx", "asset_assignment", ["expectedReturnDate"])
    op.create_index("asset_assignment_returnDate_idx", "asset_assignment", ["returnDate"])

    # Recreate asset_maintenance_log with the correct schema
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
    op.create_index("asset_maintenance_log_assetId_idx", "asset_maintenance_log", ["assetId"])
    op.create_index("asset_maintenance_log_status_idx", "asset_maintenance_log", ["status"])
    op.create_index("asset_maintenance_log_serviceDate_idx", "asset_maintenance_log", ["serviceDate"])


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
