"""sync all missing ats columns to database

Revision ID: a2b3c4d5e6f7
Revises: 716052f21ac2
Create Date: 2026-05-14 12:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "716052f21ac2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    # ── pipeline_stage: add self-referential stageId ──────────────────────
    ps_cols = _column_names("pipeline_stage")
    if "stageId" not in ps_cols:
        op.add_column(
            "pipeline_stage",
            sa.Column("stageId", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "fk_pipeline_stage_stage_id",
            "pipeline_stage",
            "pipeline_stage",
            ["stageId"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(
            op.f("ix_pipeline_stage_stageId"),
            "pipeline_stage",
            ["stageId"],
            unique=False,
        )

    # ── hiring_team: add stageId ──────────────────────────────────────────
    ht_cols = _column_names("hiring_team")
    if "stageId" not in ht_cols:
        op.add_column(
            "hiring_team",
            sa.Column("stageId", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "fk_hiring_team_stage_id",
            "hiring_team",
            "pipeline_stage",
            ["stageId"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(
            op.f("ix_hiring_team_stageId"),
            "hiring_team",
            ["stageId"],
            unique=False,
        )

    # ── candidate_application: add internalNotes + rating ─────────────────
    ca_cols = _column_names("candidate_application")
    if "internalNotes" not in ca_cols:
        op.add_column(
            "candidate_application",
            sa.Column("internalNotes", sa.Text(), nullable=True),
        )
    if "rating" not in ca_cols:
        op.add_column(
            "candidate_application",
            sa.Column("rating", sa.Integer(), nullable=True),
        )

    # ── candidate: add profile enrichment columns ─────────────────────────
    c_cols = _column_names("candidate")
    for col_name in ["portfolioUrl", "currentCompany", "currentTitle", "totalExperience"]:
        if col_name not in c_cols:
            op.add_column(
                "candidate",
                sa.Column(col_name, sa.String(), nullable=True),
            )

    # ── stage_event: add assignmentMode + teamId ──────────────────────────
    se_cols = _column_names("stage_event")
    if "assignmentMode" not in se_cols:
        op.add_column(
            "stage_event",
            sa.Column("assignmentMode", sa.String(length=32), nullable=True),
        )
    if "teamId" not in se_cols:
        op.add_column(
            "stage_event",
            sa.Column("teamId", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "fk_stage_event_team_id",
            "stage_event",
            "hiring_team",
            ["teamId"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(op.f("ix_stage_event_teamId"), "stage_event", ["teamId"], unique=False)

    # ── stage_event_participant: add approval + scheduling columns ─────────
    sep_cols = _column_names("stage_event_participant")
    if "isBackup" not in sep_cols:
        op.add_column(
            "stage_event_participant",
            sa.Column("isBackup", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "approvalStatus" not in sep_cols:
        op.add_column(
            "stage_event_participant",
            sa.Column("approvalStatus", sa.String(length=32), nullable=False, server_default="PENDING"),
        )
    if "approvedAt" not in sep_cols:
        op.add_column(
            "stage_event_participant",
            sa.Column("approvedAt", sa.DateTime(timezone=True), nullable=True),
        )
    if "rejectedAt" not in sep_cols:
        op.add_column(
            "stage_event_participant",
            sa.Column("rejectedAt", sa.DateTime(timezone=True), nullable=True),
        )
    if "scheduledTime" not in sep_cols:
        op.add_column(
            "stage_event_participant",
            sa.Column("scheduledTime", sa.DateTime(timezone=True), nullable=True),
        )

    # ── hiring_team_member: add order ─────────────────────────────────────
    htm_cols = _column_names("hiring_team_member")
    if "order" not in htm_cols:
        op.add_column(
            "hiring_team_member",
            sa.Column("order", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    htm_cols = _column_names("hiring_team_member")
    if "order" in htm_cols:
        op.drop_column("hiring_team_member", "order")

    sep_cols = _column_names("stage_event_participant")
    for col in ["scheduledTime", "rejectedAt", "approvedAt", "approvalStatus", "isBackup"]:
        if col in sep_cols:
            op.drop_column("stage_event_participant", col)

    se_cols = _column_names("stage_event")
    if "teamId" in se_cols:
        op.drop_index(op.f("ix_stage_event_teamId"), table_name="stage_event")
        op.drop_constraint("fk_stage_event_team_id", "stage_event", type_="foreignkey")
        op.drop_column("stage_event", "teamId")
    if "assignmentMode" in se_cols:
        op.drop_column("stage_event", "assignmentMode")

    c_cols = _column_names("candidate")
    for col in ["totalExperience", "currentTitle", "currentCompany", "portfolioUrl"]:
        if col in c_cols:
            op.drop_column("candidate", col)

    ca_cols = _column_names("candidate_application")
    if "rating" in ca_cols:
        op.drop_column("candidate_application", "rating")
    if "internalNotes" in ca_cols:
        op.drop_column("candidate_application", "internalNotes")

    ht_cols = _column_names("hiring_team")
    if "stageId" in ht_cols:
        op.drop_index(op.f("ix_hiring_team_stageId"), table_name="hiring_team")
        op.drop_constraint("fk_hiring_team_stage_id", "hiring_team", type_="foreignkey")
        op.drop_column("hiring_team", "stageId")

    ps_cols = _column_names("pipeline_stage")
    if "stageId" in ps_cols:
        op.drop_index(op.f("ix_pipeline_stage_stageId"), table_name="pipeline_stage")
        op.drop_constraint("fk_pipeline_stage_stage_id", "pipeline_stage", type_="foreignkey")
        op.drop_column("pipeline_stage", "stageId")
