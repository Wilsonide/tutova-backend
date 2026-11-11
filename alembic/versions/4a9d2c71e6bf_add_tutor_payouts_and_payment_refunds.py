"""add tutor payouts, payout recipients and payment refunds

Revision ID: 4a9d2c71e6bf
Revises: d4a91f6c2e10
Create Date: 2026-11-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "4a9d2c71e6bf"
down_revision: Union[str, None] = "d4a91f6c2e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# PostgreSQL ENUM definitions.
# create_type=False prevents SQLAlchemy from automatically
# issuing CREATE TYPE when creating tables.

payout_status = postgresql.ENUM(
    "REQUESTED",
    "PROCESSING",
    "PAID",
    "FAILED",
    "REVERSED",
    name="payout_status",
    create_type=False,
)

refund_status = postgresql.ENUM(
    "PENDING",
    "PROCESSING",
    "PROCESSED",
    "FAILED",
    name="refund_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # ==========================================================
    # UPDATE EXISTING PAYMENT STATUS ENUM
    # ==========================================================

    op.execute("ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'PARTIALLY_REFUNDED'")

    # ==========================================================
    # CREATE ENUM TYPES SAFELY
    # ==========================================================

    payout_status.create(
        bind,
        checkfirst=True,
    )

    refund_status.create(
        bind,
        checkfirst=True,
    )

    # ==========================================================
    # PAYOUT RECIPIENTS
    # ==========================================================

    op.create_table(
        "payout_recipients",
        sa.Column(
            "tutor_profile_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(30),
            nullable=False,
        ),
        sa.Column(
            "recipient_code",
            sa.String(100),
            nullable=False,
        ),
        sa.Column(
            "bank_name",
            sa.String(120),
            nullable=False,
        ),
        sa.Column(
            "account_name",
            sa.String(160),
            nullable=False,
        ),
        sa.Column(
            "account_last4",
            sa.String(4),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tutor_profile_id"],
            ["tutor_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tutor_profile_id"),
        sa.UniqueConstraint("recipient_code"),
    )

    # ==========================================================
    # TUTOR PAYOUTS
    # ==========================================================

    op.create_table(
        "tutor_payouts",
        sa.Column(
            "tutor_profile_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "recipient_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(30),
            nullable=False,
        ),
        sa.Column(
            "provider_reference",
            sa.String(120),
            nullable=False,
        ),
        sa.Column(
            "transfer_code",
            sa.String(120),
            nullable=True,
        ),
        sa.Column(
            "amount_minor",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
        ),
        sa.Column(
            "status",
            payout_status,
            nullable=False,
        ),
        sa.Column(
            "failure_reason",
            sa.String(500),
            nullable=True,
        ),
        sa.Column(
            "paid_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tutor_profile_id"],
            ["tutor_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["payout_recipients.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id"),
        sa.UniqueConstraint("provider_reference"),
    )

    op.create_index(
        "ix_tutor_payouts_tutor_created",
        "tutor_payouts",
        ["tutor_profile_id", "created_at"],
    )

    op.create_index(
        "ix_tutor_payouts_status",
        "tutor_payouts",
        ["status"],
    )

    # ==========================================================
    # PAYMENT REFUNDS
    # ==========================================================

    op.create_table(
        "payment_refunds",
        sa.Column(
            "payment_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(30),
            nullable=False,
        ),
        sa.Column(
            "provider_reference",
            sa.String(120),
            nullable=False,
        ),
        sa.Column(
            "amount_minor",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "tutor_share_minor",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "platform_share_minor",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
        ),
        sa.Column(
            "status",
            refund_status,
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.String(500),
            nullable=False,
        ),
        sa.Column(
            "failure_reason",
            sa.String(500),
            nullable=True,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_reference"),
    )

    op.create_index(
        "ix_payment_refunds_payment_created",
        "payment_refunds",
        ["payment_id", "created_at"],
    )

    op.create_index(
        "ix_payment_refunds_status",
        "payment_refunds",
        ["status"],
    )


def downgrade() -> None:
    # ==========================================================
    # DROP PAYMENT REFUNDS
    # ==========================================================

    op.drop_index(
        "ix_payment_refunds_status",
        table_name="payment_refunds",
    )

    op.drop_index(
        "ix_payment_refunds_payment_created",
        table_name="payment_refunds",
    )

    op.drop_table("payment_refunds")

    # ==========================================================
    # DROP TUTOR PAYOUTS
    # ==========================================================

    op.drop_index(
        "ix_tutor_payouts_status",
        table_name="tutor_payouts",
    )

    op.drop_index(
        "ix_tutor_payouts_tutor_created",
        table_name="tutor_payouts",
    )

    op.drop_table("tutor_payouts")

    # ==========================================================
    # DROP PAYOUT RECIPIENTS
    # ==========================================================

    op.drop_table("payout_recipients")

    # ==========================================================
    # DROP ENUMS
    # ==========================================================

    bind = op.get_bind()

    refund_status.drop(
        bind,
        checkfirst=True,
    )

    payout_status.drop(
        bind,
        checkfirst=True,
    )

    # PostgreSQL enum values cannot safely be removed
    # in-place. Keep PARTIALLY_REFUNDED.
