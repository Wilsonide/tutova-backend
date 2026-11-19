"""add booking pricing and payment records

Revision ID: d4a91f6c2e10
Revises: b7dfb33ce48b
Create Date: 2026-11-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a91f6c2e10"
down_revision: Union[str, None] = "b7dfb33ce48b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tutor_profiles", sa.Column("monthly_fee", sa.Numeric(12, 2), nullable=True))
    op.add_column("lesson_bookings", sa.Column("monthly_fee", sa.Numeric(12, 2), nullable=True))
    op.add_column("lesson_bookings", sa.Column("gross_amount_minor", sa.Integer(), nullable=True))
    op.add_column("lesson_bookings", sa.Column("currency", sa.String(length=3), server_default=sa.text("'NGN'"), nullable=False))

    op.create_table(
        "payments",
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("requester_user_id", sa.Uuid(), nullable=False),
        sa.Column("tutor_profile_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_reference", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("checkout_url", sa.String(length=1000), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("commission_bps", sa.Integer(), nullable=False),
        sa.Column("platform_fee_minor", sa.Integer(), nullable=False),
        sa.Column("tutor_earning_minor", sa.Integer(), nullable=False),
        sa.Column("tutor_completed_hours_at_payment", sa.Numeric(8, 2), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "PAID", "FAILED", "REFUNDED", name="payment_status"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["lesson_bookings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tutor_profile_id"], ["tutor_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("provider_reference"),
    )
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_requester_created", "payments", ["requester_user_id", "created_at"])
    op.create_index("ix_payments_tutor_created", "payments", ["tutor_profile_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_payments_tutor_created", table_name="payments")
    op.drop_index("ix_payments_requester_created", table_name="payments")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_booking_id", table_name="payments")
    op.drop_table("payments")
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.drop_column("lesson_bookings", "currency")
    op.drop_column("lesson_bookings", "gross_amount_minor")
    op.drop_column("lesson_bookings", "monthly_fee")
    op.drop_column("tutor_profiles", "monthly_fee")
