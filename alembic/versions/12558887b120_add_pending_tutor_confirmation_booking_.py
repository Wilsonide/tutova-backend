"""add pending tutor confirmation booking status

Revision ID: 12558887b120
Revises: d55c4211ce1c
Create Date: 2026-11-11 12:35:56.933071
"""

from typing import Sequence, Union

from alembic import op

revision: str = "12558887b120"
down_revision: Union[str, None] = "d55c4211ce1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TYPE booking_status
        ADD VALUE IF NOT EXISTS 'PENDING_TUTOR_CONFIRMATION'
        """
    )


def downgrade() -> None:
    # PostgreSQL does not support removing an individual enum value.
    # Keep the value in the database during downgrade.
    pass
