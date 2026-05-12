"""merge hiring team and slug heads

Revision ID: b1d92f6a7c33
Revises: 6f8b7c2d1a44, 9c7e2b4a6d13
Create Date: 2026-05-12 12:45:00.000000
"""
from typing import Sequence, Union


revision: str = "b1d92f6a7c33"
down_revision: Union[str, Sequence[str], None] = ("6f8b7c2d1a44", "9c7e2b4a6d13")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
