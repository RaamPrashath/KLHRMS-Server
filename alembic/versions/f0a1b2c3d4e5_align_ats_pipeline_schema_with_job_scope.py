"""align ats pipeline schema with job scope

Revision ID: f0a1b2c3d4e5
Revises: 8b7a8c1d2e3f
Create Date: 2026-05-14 09:30:00.000000
"""
from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "8b7a8c1d2e3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    job_columns = _column_names("job_posting")
    if "slug" not in job_columns:
        op.add_column("job_posting", sa.Column("slug", sa.String(length=160), nullable=True))

        jobs = bind.execute(
            sa.text(
                """
                SELECT id, "organizationId", title
                FROM job_posting
                ORDER BY "organizationId", "createdAt", id
                """
            )
        ).mappings().all()

        seen_job_slugs: dict[str, set[str]] = {}
        for job in jobs:
            organization_id = str(job["organizationId"])
            base_slug = _slugify(str(job["title"]))
            used = seen_job_slugs.setdefault(organization_id, set())
            candidate = base_slug
            suffix = 2
            while candidate in used:
                candidate = f"{base_slug}-{suffix}"
                suffix += 1
            used.add(candidate)
            bind.execute(
                sa.text('UPDATE job_posting SET slug = :slug WHERE id = :id'),
                {"slug": candidate, "id": job["id"]},
            )

        op.alter_column("job_posting", "slug", nullable=False)
        op.create_unique_constraint("uq_job_posting_org_slug", "job_posting", ["organizationId", "slug"])

    stage_columns = _column_names("pipeline_stage")
    if "order" in stage_columns:
        op.alter_column(
            "pipeline_stage",
            "order",
            type_=sa.Float(),
            existing_type=sa.Integer(),
            postgresql_using='"order"::double precision',
            existing_nullable=False,
        )

    constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("pipeline_stage")}
    if "uq_pipeline_stage_org_slug" in constraints:
        op.drop_constraint("uq_pipeline_stage_org_slug", "pipeline_stage", type_="unique")
    if "uq_pipeline_stage_job_slug" not in constraints:
        op.create_unique_constraint("uq_pipeline_stage_job_slug", "pipeline_stage", ["jobPostingId", "slug"])

    application_columns = _column_names("candidate_application")
    if "internalNotes" not in application_columns:
        op.add_column("candidate_application", sa.Column("internalNotes", sa.Text(), nullable=True))
    if "rating" not in application_columns:
        op.add_column("candidate_application", sa.Column("rating", sa.Integer(), nullable=True))

    candidate_columns = _column_names("candidate")
    for name in ["portfolioUrl", "currentCompany", "currentTitle", "totalExperience"]:
        if name not in candidate_columns:
            op.add_column("candidate", sa.Column(name, sa.String(), nullable=True))

    event_columns = _column_names("stage_event")
    if "assignmentMode" not in event_columns:
        op.add_column("stage_event", sa.Column("assignmentMode", sa.String(length=32), nullable=True))
    if "teamId" not in event_columns:
        op.add_column("stage_event", sa.Column("teamId", sa.String(length=36), nullable=True))
        op.create_foreign_key(
            "fk_stage_event_team_id",
            "stage_event",
            "hiring_team",
            ["teamId"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(op.f("ix_stage_event_teamId"), "stage_event", ["teamId"], unique=False)

    participant_columns = _column_names("stage_event_participant")
    if "isBackup" not in participant_columns:
        op.add_column(
            "stage_event_participant",
            sa.Column("isBackup", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "approvalStatus" not in participant_columns:
        op.add_column(
            "stage_event_participant",
            sa.Column("approvalStatus", sa.String(length=32), nullable=False, server_default="PENDING"),
        )
    if "approvedAt" not in participant_columns:
        op.add_column("stage_event_participant", sa.Column("approvedAt", sa.DateTime(timezone=True), nullable=True))
    if "rejectedAt" not in participant_columns:
        op.add_column("stage_event_participant", sa.Column("rejectedAt", sa.DateTime(timezone=True), nullable=True))
    if "scheduledTime" not in participant_columns:
        op.add_column("stage_event_participant", sa.Column("scheduledTime", sa.DateTime(timezone=True), nullable=True))

    team_columns = _column_names("hiring_team")
    if "stageId" not in team_columns:
        op.add_column("hiring_team", sa.Column("stageId", sa.String(length=36), nullable=True))
        op.create_foreign_key(
            "fk_hiring_team_stage_id",
            "hiring_team",
            "pipeline_stage",
            ["stageId"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(op.f("ix_hiring_team_stageId"), "hiring_team", ["stageId"], unique=False)

    team_member_columns = _column_names("hiring_team_member")
    if "order" not in team_member_columns:
        op.add_column(
            "hiring_team_member",
            sa.Column("order", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    op.drop_column("hiring_team_member", "order")

    op.drop_index(op.f("ix_hiring_team_stageId"), table_name="hiring_team")
    op.drop_constraint("fk_hiring_team_stage_id", "hiring_team", type_="foreignkey")
    op.drop_column("hiring_team", "stageId")

    op.drop_column("stage_event_participant", "scheduledTime")
    op.drop_column("stage_event_participant", "rejectedAt")
    op.drop_column("stage_event_participant", "approvedAt")
    op.drop_column("stage_event_participant", "approvalStatus")
    op.drop_column("stage_event_participant", "isBackup")

    op.drop_index(op.f("ix_stage_event_teamId"), table_name="stage_event")
    op.drop_constraint("fk_stage_event_team_id", "stage_event", type_="foreignkey")
    op.drop_column("stage_event", "teamId")
    op.drop_column("stage_event", "assignmentMode")

    op.drop_column("candidate", "totalExperience")
    op.drop_column("candidate", "currentTitle")
    op.drop_column("candidate", "currentCompany")
    op.drop_column("candidate", "portfolioUrl")

    op.drop_column("candidate_application", "rating")
    op.drop_column("candidate_application", "internalNotes")

    op.drop_constraint("uq_pipeline_stage_job_slug", "pipeline_stage", type_="unique")
    op.create_unique_constraint("uq_pipeline_stage_org_slug", "pipeline_stage", ["organizationId", "slug"])
    op.alter_column(
        "pipeline_stage",
        "order",
        type_=sa.Integer(),
        existing_type=sa.Float(),
        postgresql_using='round("order")::integer',
        existing_nullable=False,
    )

    op.drop_constraint("uq_job_posting_org_slug", "job_posting", type_="unique")
    op.drop_column("job_posting", "slug")
