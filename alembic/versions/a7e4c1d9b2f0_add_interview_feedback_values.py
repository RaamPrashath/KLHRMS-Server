"""add interview feedback values

Revision ID: a7e4c1d9b2f0
Revises: 4b262fe191ed
Create Date: 2026-05-15 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7e4c1d9b2f0"
down_revision: Union[str, None] = "4b262fe191ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stage_evaluation_category",
        sa.Column("valueType", sa.String(length=32), nullable=False, server_default="NUMERIC"),
    )
    op.create_table(
        "interview_feedback_value",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("feedbackId", sa.String(length=36), nullable=False),
        sa.Column("categoryId", sa.String(length=36), nullable=False),
        sa.Column("numericValue", sa.Float(), nullable=True),
        sa.Column("textValue", sa.Text(), nullable=True),
        sa.Column("booleanValue", sa.Boolean(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["categoryId"], ["stage_evaluation_category.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feedbackId"], ["interview_feedback.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feedbackId", "categoryId", name="uq_interview_feedback_value_category"),
    )
    op.create_index(op.f("ix_interview_feedback_value_categoryId"), "interview_feedback_value", ["categoryId"], unique=False)
    op.create_index(op.f("ix_interview_feedback_value_feedbackId"), "interview_feedback_value", ["feedbackId"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_feedback_value_feedbackId"), table_name="interview_feedback_value")
    op.drop_index(op.f("ix_interview_feedback_value_categoryId"), table_name="interview_feedback_value")
    op.drop_table("interview_feedback_value")
    op.drop_column("stage_evaluation_category", "valueType")
