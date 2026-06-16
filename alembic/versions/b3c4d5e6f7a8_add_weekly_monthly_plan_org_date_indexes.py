"""add composite indexes on weekly_plans and monthly_plans for org+date

Revision ID: b3c4d5e6f7a8
Revises: d151fe9ddc14
Create Date: 2026-06-16 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "d151fe9ddc14"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_weekly_plans_org_date",
        "weekly_plans",
        ["organization_id", "date"],
        unique=False,
    )
    op.create_index(
        "idx_monthly_plans_org_date",
        "monthly_plans",
        ["organization_id", "date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_monthly_plans_org_date", table_name="monthly_plans")
    op.drop_index("idx_weekly_plans_org_date", table_name="weekly_plans")
