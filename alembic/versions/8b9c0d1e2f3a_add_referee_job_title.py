"""add referee job title / occupation

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-11-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8b9c0d1e2f3a"
down_revision: Union[str, None] = "7a8b9c0d1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tutor_referees",
        sa.Column("job_title", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "tutor_referees",
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Existing referee records predate this required onboarding field.
    op.execute(
        "UPDATE tutor_referees SET job_title = 'Not provided' WHERE job_title IS NULL"
    )
    op.alter_column("tutor_referees", "job_title", nullable=False)
    op.execute(
        "UPDATE tutor_referees SET responded_at = consented_at WHERE consented_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("tutor_referees", "responded_at")
    op.drop_column("tutor_referees", "job_title")
