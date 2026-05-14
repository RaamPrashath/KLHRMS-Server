"""add dynamic categories and units

Revision ID: e9f8b4a7d3c2
Revises: cd72a8217dc2
Create Date: 2026-05-12 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision: str = 'e9f8b4a7d3c2'
down_revision: Union[str, None] = 'cd72a8217dc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create new tables ──────────────────────────────────────────────────────

    op.create_table(
        "asset_category_definition",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organizationId", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("isActive", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("asset_category_def_org_idx", "asset_category_definition", ["organizationId"])
    op.create_index("asset_category_def_org_name_idx", "asset_category_definition", ["organizationId", "name"])

    op.create_table(
        "asset_category_field_definition",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("categoryId", sa.String(36), sa.ForeignKey("asset_category_definition.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fieldName", sa.String(100), nullable=False),
        sa.Column("fieldType", sa.String(20), nullable=False),
        sa.Column("fieldOptions", JSON, nullable=True),
        sa.Column("isRequired", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("displayOrder", sa.Integer, nullable=False, server_default="0"),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("asset_cat_field_def_cat_idx", "asset_category_field_definition", ["categoryId"])

    op.create_table(
        "asset_custom_field_value",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("assetId", sa.String(36), sa.ForeignKey("asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fieldDefinitionId", sa.String(36), sa.ForeignKey("asset_category_field_definition.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Text, nullable=True),
    )
    op.create_index("asset_custom_field_asset_idx", "asset_custom_field_value", ["assetId"])
    op.create_index("asset_custom_field_def_idx", "asset_custom_field_value", ["fieldDefinitionId"])
    op.create_index("asset_custom_field_asset_def_idx", "asset_custom_field_value", ["assetId", "fieldDefinitionId"], unique=True)

    op.create_table(
        "asset_unit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("assetId", sa.String(36), sa.ForeignKey("asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("serialNumber", sa.String(255), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="AVAILABLE"),
        sa.Column("currentHolderMemberId", sa.String(36), sa.ForeignKey("member.id", ondelete="SET NULL"), nullable=True),
        sa.Column("condition", sa.String(40), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("asset_unit_asset_idx", "asset_unit", ["assetId"])
    op.create_index("asset_unit_status_idx", "asset_unit", ["status"])
    op.create_index("asset_unit_holder_idx", "asset_unit", ["currentHolderMemberId"])

    # ── Modify existing tables ─────────────────────────────────────────────────

    op.add_column(
        "asset",
        sa.Column("categoryDefinitionId", sa.String(36), nullable=True),
    )
    op.create_index("asset_category_definition_id_idx", "asset", ["categoryDefinitionId"])

    op.add_column(
        "asset_assignment",
        sa.Column("assetUnitId", sa.String(36), sa.ForeignKey("asset_unit.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("asset_assignment_unit_idx", "asset_assignment", ["assetUnitId"])

    op.add_column(
        "asset_maintenance_log",
        sa.Column("assetUnitId", sa.String(36), sa.ForeignKey("asset_unit.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("asset_maintenance_log_unit_idx", "asset_maintenance_log", ["assetUnitId"])


def downgrade() -> None:
    op.drop_index("asset_maintenance_log_unit_idx", table_name="asset_maintenance_log")
    op.drop_column("asset_maintenance_log", "assetUnitId")

    op.drop_index("asset_assignment_unit_idx", table_name="asset_assignment")
    op.drop_column("asset_assignment", "assetUnitId")

    op.drop_index("asset_category_definition_id_idx", table_name="asset")
    op.drop_column("asset", "categoryDefinitionId")

    op.drop_table("asset_unit")
    op.drop_table("asset_custom_field_value")
    op.drop_table("asset_category_field_definition")
    op.drop_table("asset_category_definition")
