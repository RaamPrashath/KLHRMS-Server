"""add_procurement_requisition_tables

Revision ID: 7c1e2c6a914f
Revises: eda69bd912f2
Create Date: 2026-05-27 22:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c1e2c6a914f"
down_revision: Union[str, None] = "eda69bd912f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_purchase_requisition",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("requestType", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requestNumber", sa.Integer(), nullable=True),
        sa.Column("raisedByMemberId", sa.String(length=36), nullable=False),
        sa.Column("approvedByMemberId", sa.String(length=36), nullable=True),
        sa.Column("approvedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejectedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewerComment", sa.Text(), nullable=True),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("requiredByDate", sa.Date(), nullable=True),
        sa.Column("estimatedUnitCost", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimatedQuantity", sa.Integer(), nullable=True),
        sa.Column("estimatedTotalCost", sa.Numeric(12, 2), nullable=True),
        sa.Column("vendorPreference", sa.String(length=160), nullable=True),
        sa.Column("urgency", sa.String(length=24), nullable=True),
        sa.Column("costCenterOrDepartmentId", sa.String(length=36), nullable=True),
        sa.Column("assetName", sa.String(length=255), nullable=True),
        sa.Column("assetCode", sa.String(length=120), nullable=True),
        sa.Column("categoryDefinitionId", sa.String(length=36), nullable=True),
        sa.Column("specificationNotes", sa.Text(), nullable=True),
        sa.Column("maintenanceTicketId", sa.String(length=36), nullable=True),
        sa.Column("assetId", sa.String(length=36), nullable=True),
        sa.Column("assetUnitId", sa.String(length=36), nullable=True),
        sa.Column("affectedEmployeeId", sa.String(length=36), nullable=True),
        sa.Column("originalPurchaseDate", sa.Date(), nullable=True),
        sa.Column("warrantyExpiryDate", sa.Date(), nullable=True),
        sa.Column("warrantyStatus", sa.String(length=24), nullable=True),
        sa.Column("replacementReason", sa.Text(), nullable=True),
        sa.Column("replacementMode", sa.String(length=40), nullable=True),
        sa.Column("ticketSnapshot", sa.JSON(), nullable=True),
        sa.Column("assetSnapshot", sa.JSON(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["affectedEmployeeId"], ["member.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approvedByMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assetId"], ["asset.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assetUnitId"], ["asset_unit.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["categoryDefinitionId"], ["asset_category_definition.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["costCenterOrDepartmentId"], ["department.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["maintenanceTicketId"], ["asset_maintenance_log.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raisedByMemberId"], ["member.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("apr_org_status_idx", "asset_purchase_requisition", ["organizationId", "status"], unique=False)
    op.create_index("apr_org_type_idx", "asset_purchase_requisition", ["organizationId", "requestType"], unique=False)
    op.create_index("apr_org_raised_idx", "asset_purchase_requisition", ["organizationId", "raisedByMemberId"], unique=False)
    op.create_index("apr_org_approved_idx", "asset_purchase_requisition", ["organizationId", "approvedByMemberId"], unique=False)
    op.create_index("apr_org_ticket_idx", "asset_purchase_requisition", ["organizationId", "maintenanceTicketId"], unique=False)

    op.create_table(
        "asset_purchase_requisition_activity_log",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("requisitionId", sa.String(length=36), nullable=False),
        sa.Column("actorId", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actorId"], ["member.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requisitionId"], ["asset_purchase_requisition.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "apral_org_requisition_idx",
        "asset_purchase_requisition_activity_log",
        ["organizationId", "requisitionId"],
        unique=False,
    )
    op.create_index(
        "apral_org_action_idx",
        "asset_purchase_requisition_activity_log",
        ["organizationId", "action"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("apral_org_action_idx", table_name="asset_purchase_requisition_activity_log")
    op.drop_index("apral_org_requisition_idx", table_name="asset_purchase_requisition_activity_log")
    op.drop_table("asset_purchase_requisition_activity_log")
    op.drop_index("apr_org_ticket_idx", table_name="asset_purchase_requisition")
    op.drop_index("apr_org_approved_idx", table_name="asset_purchase_requisition")
    op.drop_index("apr_org_raised_idx", table_name="asset_purchase_requisition")
    op.drop_index("apr_org_type_idx", table_name="asset_purchase_requisition")
    op.drop_index("apr_org_status_idx", table_name="asset_purchase_requisition")
    op.drop_table("asset_purchase_requisition")
