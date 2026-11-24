"""Add secure password reset tokens and daily progress logs.

Revision ID: d8f4a1c9b2e7
Revises: c6f2a9d1e840
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d8f4a1c9b2e7"
down_revision: Union[str, None] = "c6f2a9d1e840"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])

    op.create_table(
        "progress_log_entries",
        sa.Column("tutoring_request_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("author_type", sa.Enum("TUTOR", "LEARNER", name="progress_log_author_type", native_enum=False, create_constraint=True), nullable=False),
        sa.Column("entry_type", sa.Enum("UPDATE", "QUESTION", "MILESTONE", "CONCERN", name="progress_log_entry_type", native_enum=False, create_constraint=True), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Enum("PENDING", "REVIEWED", "FLAGGED", "RESOLVED", name="progress_log_review_status", native_enum=False, create_constraint=True), nullable=False),
        sa.Column("admin_reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("admin_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_review_notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tutoring_request_id"], ["tutoring_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["admin_reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_progress_log_request_created", "progress_log_entries", ["tutoring_request_id", "created_at"])
    op.create_index("ix_progress_log_review_created", "progress_log_entries", ["review_status", "created_at"])
    op.create_index("ix_progress_log_author_created", "progress_log_entries", ["author_user_id", "created_at"])
    op.create_index("ix_progress_log_entries_log_date", "progress_log_entries", ["log_date"])
    op.create_index("ix_progress_log_entries_review_status", "progress_log_entries", ["review_status"])

    # Keep the database CHECK constraint aligned with NotificationType.
    op.drop_constraint("notification_type_enum", "notifications", type_="check")
    op.create_check_constraint(
        "notification_type_enum",
        "notifications",
        "notification_type IN ("
        "'NEW_MATCHING_REQUEST', 'TUTOR_ACCEPTED_REQUEST', 'TUTOR_DECLINED_REQUEST', "
        "'BOOKING_REQUEST_RECEIVED', 'BOOKING_ACCEPTED', 'BOOKING_DECLINED', "
        "'BOOKING_PAYMENT_CONFIRMED', 'SESSION_AWAITING_ACKNOWLEDGEMENT', "
        "'SESSION_ACKNOWLEDGEMENT_REMINDER', "
        "'SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW', 'SESSION_ACKNOWLEDGED', "
        "'SESSION_DISPUTED', 'PROGRESS_REPORT_SUBMITTED', 'PROGRESS_LOG_ENTRY', "
        "'PROGRESS_LOG_CONCERN', 'ADMIN_NEW_TUTORING_REQUEST', 'AGREEMENT_SIGNED', "
        "'AGREEMENT_READY_FOR_LEARNER', 'AGREEMENT_READY_FOR_TUTOR')",
    )


def downgrade() -> None:
    op.drop_constraint("notification_type_enum", "notifications", type_="check")
    op.create_check_constraint(
        "notification_type_enum",
        "notifications",
        "notification_type IN ("
        "'NEW_MATCHING_REQUEST', 'TUTOR_ACCEPTED_REQUEST', 'TUTOR_DECLINED_REQUEST', "
        "'BOOKING_REQUEST_RECEIVED', 'BOOKING_ACCEPTED', 'BOOKING_DECLINED', "
        "'BOOKING_PAYMENT_CONFIRMED', 'SESSION_AWAITING_ACKNOWLEDGEMENT', "
        "'SESSION_ACKNOWLEDGEMENT_REMINDER', "
        "'SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW', 'SESSION_ACKNOWLEDGED', "
        "'SESSION_DISPUTED', 'PROGRESS_REPORT_SUBMITTED', "
        "'ADMIN_NEW_TUTORING_REQUEST', 'AGREEMENT_SIGNED', "
        "'AGREEMENT_READY_FOR_LEARNER', 'AGREEMENT_READY_FOR_TUTOR')",
    )
    op.drop_index("ix_progress_log_entries_review_status", table_name="progress_log_entries")
    op.drop_index("ix_progress_log_entries_log_date", table_name="progress_log_entries")
    op.drop_index("ix_progress_log_author_created", table_name="progress_log_entries")
    op.drop_index("ix_progress_log_review_created", table_name="progress_log_entries")
    op.drop_index("ix_progress_log_request_created", table_name="progress_log_entries")
    op.drop_table("progress_log_entries")
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
