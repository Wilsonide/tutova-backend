"""store split monthly commission snapshots

Revision ID: e2f6a9c4b731
Revises: 7a8b9c0d1e2f
Create Date: 2026-11-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2f6a9c4b731"
down_revision: Union[str, None] = "3c4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep existing payment values intact. Before this migration, amount_minor
    # represented the tutoring charge and platform_fee_minor was deducted from
    # that amount. New rows store the learner total and a separate breakdown.
    op.add_column(
        "payments",
        sa.Column("tutoring_amount_minor", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "payments",
        sa.Column("tutor_commission_minor", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "payments",
        sa.Column("learner_fee_minor", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE payments SET tutoring_amount_minor = amount_minor "
        "WHERE tutoring_amount_minor = 0"
    )

    op.add_column(
        "monthly_tutoring_arrangements",
        sa.Column("tutor_commission_minor", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "monthly_tutoring_arrangements",
        sa.Column("learner_fee_minor", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "monthly_tutoring_arrangements",
        sa.Column(
            "commission_schedule",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("monthly_tutoring_arrangements", "commission_schedule")
    op.drop_column("monthly_tutoring_arrangements", "learner_fee_minor")
    op.drop_column("monthly_tutoring_arrangements", "tutor_commission_minor")
    op.drop_column("payments", "learner_fee_minor")
    op.drop_column("payments", "tutor_commission_minor")
    op.drop_column("payments", "tutoring_amount_minor")
