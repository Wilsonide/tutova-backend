"""add full referee reference form and safeguarding review audit

Revision ID: 3c4d5e6f7a8b
Revises: 8b9c0d1e2f3a
Create Date: 2026-11-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3c4d5e6f7a8b"
down_revision: Union[str, None] = "8b9c0d1e2f3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A submitted invitation is single-use. NULL removes the token hash after
    # submission/expiry while preserving the referee response and audit record.
    op.alter_column(
        "tutor_referees",
        "consent_token_hash",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    # Previously completed/expired invitations must not retain usable hashes.
    op.execute(
        "UPDATE tutor_referees SET consent_token_hash = NULL "
        "WHERE status <> 'PENDING' OR responded_at IS NOT NULL"
    )
    op.add_column(
        "tutor_referees",
        sa.Column("reference_response", sa.JSON(), nullable=True),
    )
    op.add_column(
        "tutor_referees",
        sa.Column("reference_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tutor_referees",
        sa.Column("reference_ip_address", sa.String(length=45), nullable=True),
    )
    op.add_column(
        "tutor_referees",
        sa.Column(
            "safeguarding_review_required",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "tutor_referees",
        sa.Column(
            "safeguarding_review_reasons",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )

    op.add_column(
        "tutor_verifications",
        sa.Column(
            "safeguarding_review_required",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "tutor_verifications",
        sa.Column(
            "safeguarding_review_reasons",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "tutor_verifications",
        sa.Column("safeguarding_reviewed_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "tutor_verifications",
        sa.Column("safeguarding_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tutor_verifications",
        sa.Column("safeguarding_review_notes", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tutor_verifications_safeguarding_reviewed_by_users",
        "tutor_verifications",
        "users",
        ["safeguarding_reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Restore non-null uniqueness with inert, non-authenticating hashes for
    # already-consumed links. These values cannot be derived from old tokens.
    op.execute(
        "UPDATE tutor_referees "
        "SET consent_token_hash = lpad(replace(id::text, '-', ''), 64, '0') "
        "WHERE consent_token_hash IS NULL"
    )
    op.drop_constraint(
        "fk_tutor_verifications_safeguarding_reviewed_by_users",
        "tutor_verifications",
        type_="foreignkey",
    )
    for column in (
        "safeguarding_review_notes",
        "safeguarding_reviewed_at",
        "safeguarding_reviewed_by",
        "safeguarding_review_reasons",
        "safeguarding_review_required",
    ):
        op.drop_column("tutor_verifications", column)

    for column in (
        "safeguarding_review_reasons",
        "safeguarding_review_required",
        "reference_ip_address",
        "reference_submitted_at",
        "reference_response",
    ):
        op.drop_column("tutor_referees", column)

    op.alter_column(
        "tutor_referees",
        "consent_token_hash",
        existing_type=sa.String(length=64),
        nullable=False,
    )
