"""add tutor and learner lesson progress reports

Revision ID: e21a7b9c4d10
Revises: 3c4d5e6f7a8b
Create Date: 2026-11-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "e21a7b9c4d10"
down_revision: Union[str, None] = "f3a91c7d2e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing bookings retain their legacy acknowledgement path; newly-created
    # bookings receive the ORM default True and require both reports.
    op.add_column("lesson_bookings", sa.Column("progress_reports_required", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.alter_column("lesson_bookings", "progress_reports_required", server_default=sa.text("true"))
    op.drop_constraint("notification_type_enum", "notifications", type_="check")
    op.create_check_constraint(
        "notification_type_enum", "notifications",
        "notification_type IN ('NEW_MATCHING_REQUEST', 'TUTOR_ACCEPTED_REQUEST', 'BOOKING_REQUEST_RECEIVED', 'BOOKING_ACCEPTED', 'BOOKING_DECLINED', 'SESSION_AWAITING_ACKNOWLEDGEMENT', 'SESSION_ACKNOWLEDGEMENT_REMINDER', 'SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW', 'SESSION_ACKNOWLEDGED', 'SESSION_DISPUTED', 'PROGRESS_REPORT_SUBMITTED', 'ADMIN_NEW_TUTORING_REQUEST')",
    )
    op.create_table(
        "progress_reports",
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("author_type", sa.Enum("TUTOR", "LEARNER", name="progress_report_author", native_enum=False, create_constraint=True), nullable=False),
        sa.Column("lesson_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("topic_covered", sa.String(500), nullable=False),
        sa.Column("learning_objectives", sa.Text(), nullable=True),
        sa.Column("activities", sa.Text(), nullable=True),
        sa.Column("learner_performance", sa.Text(), nullable=True),
        sa.Column("challenges", sa.Text(), nullable=True),
        sa.Column("next_steps", sa.Text(), nullable=True),
        sa.Column("attendance_confirmed", sa.Boolean(), nullable=False),
        sa.Column("satisfaction_rating", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("issue_reported", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("issue_details", sa.Text(), nullable=True),
        sa.Column("review_status", sa.Enum("PENDING", "ACKNOWLEDGED", "FLAGGED", "RESOLVED", name="progress_report_review_status", native_enum=False, create_constraint=True), nullable=False),
        sa.Column("admin_reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("admin_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_review_notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["lesson_bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["admin_reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id", "author_user_id", name="uq_progress_report_booking_author"),
    )
    op.create_index("ix_progress_reports_booking_created", "progress_reports", ["booking_id", "created_at"])
    op.create_index("ix_progress_reports_review_status", "progress_reports", ["review_status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_progress_reports_review_status", table_name="progress_reports")
    op.drop_index("ix_progress_reports_booking_created", table_name="progress_reports")
    op.drop_table("progress_reports")
    op.drop_column("lesson_bookings", "progress_reports_required")
    op.drop_constraint("notification_type_enum", "notifications", type_="check")
    op.create_check_constraint(
        "notification_type_enum", "notifications",
        "notification_type IN ('NEW_MATCHING_REQUEST', 'TUTOR_ACCEPTED_REQUEST', 'BOOKING_REQUEST_RECEIVED', 'BOOKING_ACCEPTED', 'BOOKING_DECLINED', 'SESSION_AWAITING_ACKNOWLEDGEMENT', 'SESSION_ACKNOWLEDGEMENT_REMINDER', 'SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW', 'SESSION_ACKNOWLEDGED', 'SESSION_DISPUTED')",
    )
