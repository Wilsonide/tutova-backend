"""allow monthly installment payouts per tutoring contract

Revision ID: df47a8b12c60
Revises: c31f8a7d9e20
Create Date: 2026-11-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "df47a8b12c60"
down_revision: Union[str, None] = "c31f8a7d9e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("tutor_payouts_payment_id_key", "tutor_payouts", type_="unique")
    op.add_column("tutor_payouts", sa.Column("earning_period_start", sa.Date(), nullable=True))
    op.add_column("tutor_payouts", sa.Column("earning_period_end", sa.Date(), nullable=True))
    op.create_unique_constraint(
        "uq_tutor_payout_payment_earning_period",
        "tutor_payouts",
        ["payment_id", "earning_period_start"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_tutor_payout_payment_earning_period", "tutor_payouts", type_="unique"
    )
    op.drop_column("tutor_payouts", "earning_period_end")
    op.drop_column("tutor_payouts", "earning_period_start")
    op.create_unique_constraint(
        "tutor_payouts_payment_id_key", "tutor_payouts", ["payment_id"]
    )
