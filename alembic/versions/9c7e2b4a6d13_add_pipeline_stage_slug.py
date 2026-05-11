"""add pipeline stage slug

Revision ID: 9c7e2b4a6d13
Revises: f43cf5b85a2b
Create Date: 2026-05-11 13:15:00.000000
"""
from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "9c7e2b4a6d13"
down_revision: Union[str, None] = "f43cf5b85a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "stage"


def upgrade() -> None:
    op.add_column("pipeline_stage", sa.Column("slug", sa.String(length=160), nullable=True))

    connection = op.get_bind()
    stages = connection.execute(
        sa.text(
            """
            SELECT id, "organizationId", name
            FROM pipeline_stage
            ORDER BY "organizationId", "createdAt", id
            """
        )
    ).mappings().all()

    seen: dict[str, set[str]] = {}
    for stage in stages:
        organization_id = str(stage["organizationId"])
        used = seen.setdefault(organization_id, set())
        base_slug = _slugify(str(stage["name"]))
        candidate = base_slug
        index = 2
        while candidate in used:
            candidate = f"{base_slug}-{index}"
            index += 1
        used.add(candidate)
        connection.execute(
            sa.text("UPDATE pipeline_stage SET slug = :slug WHERE id = :id"),
            {"slug": candidate, "id": stage["id"]},
        )

    op.alter_column("pipeline_stage", "slug", nullable=False)
    op.create_unique_constraint(
        "uq_pipeline_stage_org_slug",
        "pipeline_stage",
        ["organizationId", "slug"],
    )
    op.create_index("ix_pipeline_stage_org_slug", "pipeline_stage", ["organizationId", "slug"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pipeline_stage_org_slug", table_name="pipeline_stage")
    op.drop_constraint("uq_pipeline_stage_org_slug", "pipeline_stage", type_="unique")
    op.drop_column("pipeline_stage", "slug")
