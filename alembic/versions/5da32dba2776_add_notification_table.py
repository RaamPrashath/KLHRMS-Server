"""add_notification_table

Revision ID: 5da32dba2776
Revises: c4d5e6f7a8b0
Create Date: 2026-06-08 11:46:23.384269
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5da32dba2776'
down_revision: Union[str, None] = 'c4d5e6f7a8b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("memberId", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="UNREAD"),
        sa.Column("actionUrl", sa.String(length=500), nullable=True),
        sa.Column("entityType", sa.String(length=80), nullable=True),
        sa.Column("entityId", sa.String(length=36), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("readAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["memberId"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("notification_org_idx", "notification", ["organizationId"], unique=False)
    op.create_index("notification_member_idx", "notification", ["memberId"], unique=False)
    op.create_index("notification_status_idx", "notification", ["status"], unique=False)
    op.create_index("notification_created_at_idx", "notification", ["createdAt"], unique=False)
    op.create_index(
        "notification_org_member_status_idx",
        "notification",
        ["organizationId", "memberId", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("notification_org_member_status_idx", table_name="notification")
    op.drop_index("notification_created_at_idx", table_name="notification")
    op.drop_index("notification_status_idx", table_name="notification")
    op.drop_index("notification_member_idx", table_name="notification")
    op.drop_index("notification_org_idx", table_name="notification")
    op.drop_table("notification")
