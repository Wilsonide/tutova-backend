"""add monthly tutoring contracts and booking payment links

Revision ID: c31f8a7d9e20
Revises: a710420e305e
Create Date: 2026-11-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c31f8a7d9e20"
down_revision: Union[str, None] = "a710420e305e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the PostgreSQL enum once, even when an earlier failed/manual
    # schema operation has already left the type in the database. Setting
    # create_type=False prevents create_table() from trying to create it again.
    arrangement_status = postgresql.ENUM(
        "PENDING_PAYMENT", "ACTIVE", "COMPLETED", "CANCELLED", "EXPIRED",
        name="monthly_arrangement_status",
        create_type=False,
    )
    arrangement_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "monthly_tutoring_arrangements",
        sa.Column("tutoring_request_id", sa.Uuid(), nullable=False),
        sa.Column("tutor_profile_id", sa.Uuid(), nullable=False),
        sa.Column("requester_user_id", sa.Uuid(), nullable=False),
        sa.Column("monthly_fee_minor", sa.Integer(), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("commission_bps", sa.Integer(), nullable=False),
        sa.Column("platform_fee_minor", sa.Integer(), nullable=False),
        sa.Column("tutor_earning_minor", sa.Integer(), nullable=False),
        sa.Column("completed_months_at_creation", sa.Numeric(8, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="NGN", nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", arrangement_status, server_default="PENDING_PAYMENT", nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("monthly_fee_minor > 0", name="ck_monthly_arrangement_fee_positive"),
        sa.CheckConstraint("period_end >= period_start", name="ck_monthly_arrangement_period"),
        sa.CheckConstraint("duration_months >= 1 AND duration_months <= 3", name="ck_monthly_arrangement_duration"),
        sa.CheckConstraint("commission_bps >= 0 AND commission_bps <= 10000", name="ck_monthly_arrangement_commission"),
        sa.CheckConstraint("platform_fee_minor >= 0 AND tutor_earning_minor > 0", name="ck_monthly_arrangement_earnings"),
        sa.ForeignKeyConstraint(["tutoring_request_id"], ["tutoring_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tutor_profile_id"], ["tutor_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tutoring_request_id", "period_start", name="uq_monthly_arrangement_request_period"),
    )
    op.create_index("ix_monthly_arrangement_requester_period", "monthly_tutoring_arrangements", ["requester_user_id", "period_start"])
    op.create_index("ix_monthly_arrangement_tutor_period", "monthly_tutoring_arrangements", ["tutor_profile_id", "period_start"])
    op.create_index("ix_monthly_arrangement_status_period", "monthly_tutoring_arrangements", ["status", "period_end"])
    op.create_index("ix_monthly_tutoring_arrangements_status", "monthly_tutoring_arrangements", ["status"])

    op.add_column("lesson_bookings", sa.Column("monthly_arrangement_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_lesson_bookings_monthly_arrangement_id",
        "lesson_bookings", "monthly_tutoring_arrangements",
        ["monthly_arrangement_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_lesson_bookings_monthly_arrangement_id", "lesson_bookings", ["monthly_arrangement_id"])

    op.add_column("payments", sa.Column("monthly_arrangement_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_payments_monthly_arrangement_id",
        "payments", "monthly_tutoring_arrangements",
        ["monthly_arrangement_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_unique_constraint("uq_payments_monthly_arrangement_id", "payments", ["monthly_arrangement_id"])

    # Keep the historical hours snapshot untouched for audit. New commission
    # calculations use this separate completed-months snapshot.
    op.add_column(
        "payments",
        sa.Column(
            "tutor_completed_months_at_payment",
            sa.Numeric(8, 2),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("payments", "tutor_completed_months_at_payment")
    op.drop_constraint("uq_payments_monthly_arrangement_id", "payments", type_="unique")
    op.drop_constraint("fk_payments_monthly_arrangement_id", "payments", type_="foreignkey")
    op.drop_column("payments", "monthly_arrangement_id")
    op.drop_index("ix_lesson_bookings_monthly_arrangement_id", table_name="lesson_bookings")
    op.drop_constraint("fk_lesson_bookings_monthly_arrangement_id", "lesson_bookings", type_="foreignkey")
    op.drop_column("lesson_bookings", "monthly_arrangement_id")
    op.drop_index("ix_monthly_tutoring_arrangements_status", table_name="monthly_tutoring_arrangements")
    op.drop_index("ix_monthly_arrangement_status_period", table_name="monthly_tutoring_arrangements")
    op.drop_index("ix_monthly_arrangement_tutor_period", table_name="monthly_tutoring_arrangements")
    op.drop_index("ix_monthly_arrangement_requester_period", table_name="monthly_tutoring_arrangements")
    op.drop_table("monthly_tutoring_arrangements")
    postgresql.ENUM(
        name="monthly_arrangement_status",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
