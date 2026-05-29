"""add_procurement_po_template_table

Revision ID: c3f4a5b6d7e8
Revises: b8e4c1f0a9d2
Create Date: 2026-05-28 18:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3f4a5b6d7e8"
down_revision: Union[str, None] = "b8e4c1f0a9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "procurement_purchase_order_template",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False, server_default="Default Purchase Order"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="ACTIVE"),
        sa.Column("templateVersion", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("templateData", sa.JSON(), nullable=False),
        sa.Column("lastEditedByMemberId", sa.String(length=36), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lastEditedByMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organizationId", name="procurement_po_template_org_key"),
    )
    op.create_index(
        "procurement_po_template_org_status_idx",
        "procurement_purchase_order_template",
        ["organizationId", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("procurement_po_template_org_status_idx", table_name="procurement_purchase_order_template")
    op.drop_table("procurement_purchase_order_template")
