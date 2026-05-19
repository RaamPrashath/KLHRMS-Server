"""add job posting requisition link

Revision ID: d2e4f6a8b901
Revises: c9d4e2a7f501
Create Date: 2026-05-17 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2e4f6a8b901"
down_revision: str | Sequence[str] | None = "c9d4e2a7f501"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_posting",
        sa.Column("requisitionId", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_job_posting_requisitionId"),
        "job_posting",
        ["requisitionId"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("job_posting_requisitionId_fkey"),
        "job_posting",
        "job_requisition",
        ["requisitionId"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("job_posting_requisitionId_fkey"),
        "job_posting",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_job_posting_requisitionId"), table_name="job_posting")
    op.drop_column("job_posting", "requisitionId")
