"""add durable tutor approval timestamp for commission tenure

Revision ID: f3a91c7d2e40
Revises: e2f6a9c4b731
Create Date: 2026-11-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a91c7d2e40"
down_revision: Union[str, None] = "e2f6a9c4b731"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tutor_verifications",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Preserve the best available historical approval timestamp for tutors
    # already approved before this migration. Never infer it from account creation.
    op.execute(
        "UPDATE tutor_verifications "
        "SET approved_at = reviewed_at "
        "WHERE status = 'APPROVED' AND reviewed_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("tutor_verifications", "approved_at")
