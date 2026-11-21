"""Allow payments before booking creation.

Revision ID: c6f2a9d1e840
Revises: b5e8a1c7d930
"""

import sqlalchemy as sa

from alembic import op

revision = "c6f2a9d1e840"
down_revision = "b5e8a1c7d930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "payments",
        "booking_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "payments",
        "booking_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
