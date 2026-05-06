"""merge monthly plan and timesheets heads

Revision ID: 8e4d8fe3b1a1
Revises: 4c4b4e0c2c5d, b7005c6c1bf0
Create Date: 2026-05-06 18:52:00.000000
"""

from typing import Sequence, Union


revision: str = "8e4d8fe3b1a1"
down_revision: Union[str, tuple[str, str], None] = ("4c4b4e0c2c5d", "b7005c6c1bf0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
