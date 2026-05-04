"""rename_tables_to_lowercase (SAFE VERSION)

Revision ID: ad1e40baa235
Revises: 5cab7470aedf
Create Date: 2026-05-04
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = 'ad1e40baa235'
down_revision: Union[str, None] = '5cab7470aedf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def constraint_exists(conn, name: str) -> bool:
    return conn.execute(text("""
        SELECT 1 FROM pg_constraint WHERE conname = :name
    """), {"name": name}).scalar() is not None


# ---------------------------------------------------------
# UPGRADE
# ---------------------------------------------------------
def upgrade() -> None:
    conn = op.get_bind()

    # -----------------------------------------------------
    # 1. Rename tables safely (only if they exist)
    # -----------------------------------------------------
    op.execute('ALTER TABLE IF EXISTS "Organization" RENAME TO organization')
    op.execute('ALTER TABLE IF EXISTS "Member" RENAME TO member')
    op.execute('ALTER TABLE IF EXISTS "Role" RENAME TO role')

    # -----------------------------------------------------
    # 2. Constraints (create ONLY if missing)
    # -----------------------------------------------------

    # organization
    if not constraint_exists(conn, "organization_slug_key"):
        op.create_unique_constraint(
            "organization_slug_key",
            "organization",
            ["slug"]
        )

    # role
    if not constraint_exists(conn, "role_organizationId_fkey"):
        op.create_foreign_key(
            "role_organizationId_fkey",
            "role",
            "organization",
            ["organizationId"],
            ["id"],
            ondelete="CASCADE"
        )

    if not constraint_exists(conn, "role_organizationId_id_key"):
        op.create_unique_constraint(
            "role_organizationId_id_key",
            "role",
            ["organizationId", "id"]
        )

    if not constraint_exists(conn, "role_organizationId_name_key"):
        op.create_unique_constraint(
            "role_organizationId_name_key",
            "role",
            ["organizationId", "name"]
        )

    # member
    if not constraint_exists(conn, "member_organizationId_fkey"):
        op.create_foreign_key(
            "member_organizationId_fkey",
            "member",
            "organization",
            ["organizationId"],
            ["id"],
            ondelete="CASCADE"
        )

    if not constraint_exists(conn, "member_userId_fkey"):
        op.create_foreign_key(
            "member_userId_fkey",
            "member",
            "user",
            ["userId"],
            ["id"],
            ondelete="CASCADE"
        )

    if not constraint_exists(conn, "member_organizationId_roleId_fkey"):
        op.create_foreign_key(
            "member_organizationId_roleId_fkey",
            "member",
            "role",
            ["organizationId", "roleId"],
            ["organizationId", "id"]
        )

    if not constraint_exists(conn, "member_organizationId_userId_key"):
        op.create_unique_constraint(
            "member_organizationId_userId_key",
            "member",
            ["organizationId", "userId"]
        )

    # -----------------------------------------------------
    # 3. Indexes (safe creation)
    # -----------------------------------------------------
    op.execute("""
        CREATE INDEX IF NOT EXISTS member_organizationId_idx
        ON member ("organizationId")
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS member_userId_idx
        ON member ("userId")
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS role_organizationId_idx
        ON role ("organizationId")
    """)


# ---------------------------------------------------------
# DOWNGRADE (simple + safe)
# ---------------------------------------------------------
def downgrade() -> None:
    # Reverse rename (safe)
    op.execute('ALTER TABLE IF EXISTS organization RENAME TO "Organization"')
    op.execute('ALTER TABLE IF EXISTS member RENAME TO "Member"')
    op.execute('ALTER TABLE IF EXISTS role RENAME TO "Role"')