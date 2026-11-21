"""create lesson bookings only after successful payment

Revision ID: 9a7c2d1e4f60
Revises: f6b2c8d4a910
Create Date: 2026-11-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "9a7c2d1e4f60"
down_revision: Union[str, None] = "f6b2c8d4a910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments", sa.Column("tutoring_request_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "payments",
        sa.Column("proposed_start_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "payments", sa.Column("proposed_duration_minutes", sa.Integer(), nullable=True)
    )
    op.add_column(
        "payments",
        sa.Column("proposed_lesson_notes", sa.String(length=3000), nullable=True),
    )
    op.add_column(
        "payments", sa.Column("proposed_contract_months", sa.Integer(), nullable=True)
    )
    op.create_index(
        "ix_payments_tutoring_request_id", "payments", ["tutoring_request_id"]
    )
    op.create_foreign_key(
        "fk_payments_tutoring_request_id_tutoring_requests",
        "payments",
        "tutoring_requests",
        ["tutoring_request_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    # A single arrangement can have multiple payment attempts (e.g. a failed
    # Paystack attempt followed by a retry). Keep each attempt for auditability.
    op.drop_constraint("uq_payments_monthly_arrangement_id", "payments", type_="unique")
    op.create_index(
        "ix_payments_monthly_arrangement_id", "payments", ["monthly_arrangement_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_payments_monthly_arrangement_id", table_name="payments")
    op.create_unique_constraint(
        "uq_payments_monthly_arrangement_id", "payments", ["monthly_arrangement_id"]
    )
    op.drop_constraint(
        "fk_payments_tutoring_request_id_tutoring_requests",
        "payments",
        type_="foreignkey",
    )
    op.drop_index("ix_payments_tutoring_request_id", table_name="payments")
    op.drop_column("payments", "proposed_contract_months")
    op.drop_column("payments", "proposed_lesson_notes")
    op.drop_column("payments", "proposed_duration_minutes")
    op.drop_column("payments", "proposed_start_at")
    op.drop_column("payments", "tutoring_request_id")
