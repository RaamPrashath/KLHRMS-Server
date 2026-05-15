"""merge feedback and schema sync heads

Revision ID: b8f2d6a41c90
Revises: a7e4c1d9b2f0, f4c5c5b65399
Create Date: 2026-05-15 00:00:00.000000
"""

from typing import Sequence, Union


revision: str = "b8f2d6a41c90"
down_revision: Union[str, tuple[str, str], None] = ("a7e4c1d9b2f0", "f4c5c5b65399")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
