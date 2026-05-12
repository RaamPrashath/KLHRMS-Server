"""harmonize hiring team schema

Revision ID: c4e5f6a7b8d9
Revises: b1d92f6a7c33
Create Date: 2026-05-12 13:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e5f6a7b8d9"
down_revision: Union[str, None] = "b1d92f6a7c33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("hiring_team_member"):
        member_columns = _get_column_names("hiring_team_member")

        if "teamId" in member_columns and "hiringTeamId" not in member_columns:
            op.alter_column("hiring_team_member", "teamId", new_column_name="hiringTeamId")

        member_columns = _get_column_names("hiring_team_member")
        if "role" not in member_columns:
            op.add_column("hiring_team_member", sa.Column("role", sa.String(length=120), nullable=True))

    if inspector.has_table("hiring_team"):
        team_columns = {column["name"]: column for column in inspector.get_columns("hiring_team")}
        name_column = team_columns.get("name")
        if name_column is not None and getattr(name_column["type"], "length", None) != 255:
            op.alter_column("hiring_team", "name", type_=sa.String(length=255), existing_nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("hiring_team"):
        team_columns = {column["name"]: column for column in inspector.get_columns("hiring_team")}
        name_column = team_columns.get("name")
        if name_column is not None and getattr(name_column["type"], "length", None) != 160:
            op.alter_column("hiring_team", "name", type_=sa.String(length=160), existing_nullable=False)

    if inspector.has_table("hiring_team_member"):
        member_columns = _get_column_names("hiring_team_member")
        if "role" in member_columns:
            op.drop_column("hiring_team_member", "role")

        member_columns = _get_column_names("hiring_team_member")
        if "hiringTeamId" in member_columns and "teamId" not in member_columns:
            op.alter_column("hiring_team_member", "hiringTeamId", new_column_name="teamId")
