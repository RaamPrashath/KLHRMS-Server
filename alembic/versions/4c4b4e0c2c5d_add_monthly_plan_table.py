"""add monthly plan table

Revision ID: 4c4b4e0c2c5d
Revises: e5b0768bcee0
Create Date: 2026-05-06 18:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4c4b4e0c2c5d"
down_revision: Union[str, None] = "e5b0768bcee0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monthly_plans",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("work_location", sa.String(length=40), nullable=False),
        sa.Column("project", sa.String(length=200), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            "date",
            name="uq_monthly_plan_org_user_date",
        ),
    )
    op.create_index(op.f("ix_monthly_plans_organization_id"), "monthly_plans", ["organization_id"], unique=False)
    op.create_index(op.f("ix_monthly_plans_user_id"), "monthly_plans", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_monthly_plans_user_id"), table_name="monthly_plans")
    op.drop_index(op.f("ix_monthly_plans_organization_id"), table_name="monthly_plans")
    op.drop_table("monthly_plans")
