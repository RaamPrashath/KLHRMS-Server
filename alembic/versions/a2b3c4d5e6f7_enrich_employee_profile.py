"""enrich employee profile with extended Microsoft Entra fields

Adds a user_id foreign key and the full set of extended Entra user attributes
(directReports, businessPhones, address, hire date, etc.) to support a
comprehensive employee detail page.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-05 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employee",
        sa.Column("user_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_employee_user_id", "employee", ["user_id"], unique=False
    )
    op.create_foreign_key(
        "fk_employee_user_id",
        "employee",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "employee",
        sa.Column("business_phones", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("given_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("surname", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("street_address", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("city", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("state", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("postal_code", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("country", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("company_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("employee_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("employee_hire_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("usage_location", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("user_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column("preferred_language", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "employee",
        sa.Column(
            "created_date_time",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "employee",
        sa.Column("manager_chain", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employee", "manager_chain")
    op.drop_column("employee", "created_date_time")
    op.drop_column("employee", "preferred_language")
    op.drop_column("employee", "user_type")
    op.drop_column("employee", "usage_location")
    op.drop_column("employee", "employee_hire_date")
    op.drop_column("employee", "employee_type")
    op.drop_column("employee", "company_name")
    op.drop_column("employee", "country")
    op.drop_column("employee", "postal_code")
    op.drop_column("employee", "state")
    op.drop_column("employee", "city")
    op.drop_column("employee", "street_address")
    op.drop_column("employee", "surname")
    op.drop_column("employee", "given_name")
    op.drop_column("employee", "business_phones")
    op.drop_constraint("fk_employee_user_id", "employee", type_="foreignkey")
    op.drop_index("ix_employee_user_id", table_name="employee")
    op.drop_column("employee", "user_id")
