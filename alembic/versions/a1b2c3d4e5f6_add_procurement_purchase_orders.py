"""add_procurement_purchase_orders

Revision ID: a1b2c3d4e5f6
Revises: 7c1e2c6a914f
Create Date: 2026-05-28 12:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7c1e2c6a914f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_purchase_order",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("requisitionId", sa.String(length=36), nullable=False),
        sa.Column("poNumber", sa.String(length=64), nullable=False),
        sa.Column("formatKey", sa.String(length=64), nullable=False, server_default="STANDARD"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="GENERATED"),
        sa.Column("storageBucket", sa.String(length=120), nullable=False),
        sa.Column("storagePath", sa.Text(), nullable=False),
        sa.Column("fileName", sa.String(length=255), nullable=False),
        sa.Column("recipientMemberId", sa.String(length=36), nullable=True),
        sa.Column("recipientEmail", sa.String(length=255), nullable=False),
        sa.Column("generatedByMemberId", sa.String(length=36), nullable=True),
        sa.Column("generatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sentAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("emailSubject", sa.String(length=255), nullable=True),
        sa.Column("emailError", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["generatedByMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipientMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requisitionId"], ["asset_purchase_requisition.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organizationId", "poNumber", name="apo_org_po_number_key"),
    )
    op.create_index("apo_org_req_idx", "asset_purchase_order", ["organizationId", "requisitionId"], unique=False)
    op.create_index("apo_org_status_idx", "asset_purchase_order", ["organizationId", "status"], unique=False)
    op.create_index(
        "apo_org_recipient_idx", "asset_purchase_order", ["organizationId", "recipientMemberId"], unique=False
    )


def downgrade() -> None:
    op.drop_index("apo_org_recipient_idx", table_name="asset_purchase_order")
    op.drop_index("apo_org_status_idx", table_name="asset_purchase_order")
    op.drop_index("apo_org_req_idx", table_name="asset_purchase_order")
    op.drop_table("asset_purchase_order")
