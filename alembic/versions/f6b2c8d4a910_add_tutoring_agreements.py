"""add tutoring agreement review and acceptance workflow

Revision ID: f6b2c8d4a910
Revises: e21a7b9c4d10
Create Date: 2026-11-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f6b2c8d4a910"
down_revision: Union[str, None] = "e21a7b9c4d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOTIFICATION_TYPES = "'NEW_MATCHING_REQUEST', 'TUTOR_ACCEPTED_REQUEST', 'BOOKING_REQUEST_RECEIVED', 'BOOKING_ACCEPTED', 'BOOKING_DECLINED', 'BOOKING_PAYMENT_CONFIRMED', 'SESSION_AWAITING_ACKNOWLEDGEMENT', 'SESSION_ACKNOWLEDGEMENT_REMINDER', 'SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW', 'SESSION_ACKNOWLEDGED', 'SESSION_DISPUTED', 'PROGRESS_REPORT_SUBMITTED', 'ADMIN_NEW_TUTORING_REQUEST', 'AGREEMENT_READY_FOR_TUTOR', 'AGREEMENT_READY_FOR_LEARNER', 'AGREEMENT_SIGNED'"


def upgrade() -> None:
    op.drop_constraint("notification_type_enum", "notifications", type_="check")
    op.create_check_constraint("notification_type_enum", "notifications", f"notification_type IN ({NOTIFICATION_TYPES})")
    op.create_table(
        "tutoring_agreements",
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("tutoring_request_id", sa.Uuid(), nullable=False),
        sa.Column("requester_user_id", sa.Uuid(), nullable=False),
        sa.Column("tutor_profile_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Enum("PENDING_TUTOR_REVIEW", "PENDING_LEARNER_APPROVAL", "CHANGES_REQUESTED", "SIGNED", "CANCELLED", name="tutoring_agreement_status", native_enum=False, create_constraint=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("revision_history", sa.JSON(), nullable=False),
        sa.Column("tutor_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("learner_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tutor_notes", sa.Text(), nullable=True),
        sa.Column("learner_notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["lesson_bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tutoring_request_id"], ["tutoring_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tutor_profile_id"], ["tutor_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
    )
    op.create_index("ix_tutoring_agreements_tutoring_request_id", "tutoring_agreements", ["tutoring_request_id"])
    op.create_index("ix_tutoring_agreements_requester_user_id", "tutoring_agreements", ["requester_user_id"])
    op.create_index("ix_tutoring_agreements_tutor_profile_id", "tutoring_agreements", ["tutor_profile_id"])
    op.create_index("ix_tutoring_agreements_status", "tutoring_agreements", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tutoring_agreements_status", table_name="tutoring_agreements")
    op.drop_index("ix_tutoring_agreements_tutor_profile_id", table_name="tutoring_agreements")
    op.drop_index("ix_tutoring_agreements_requester_user_id", table_name="tutoring_agreements")
    op.drop_index("ix_tutoring_agreements_tutoring_request_id", table_name="tutoring_agreements")
    op.drop_table("tutoring_agreements")
    op.drop_constraint("notification_type_enum", "notifications", type_="check")
    op.create_check_constraint("notification_type_enum", "notifications", "notification_type IN ('NEW_MATCHING_REQUEST', 'TUTOR_ACCEPTED_REQUEST', 'BOOKING_REQUEST_RECEIVED', 'BOOKING_ACCEPTED', 'BOOKING_DECLINED', 'BOOKING_PAYMENT_CONFIRMED', 'SESSION_AWAITING_ACKNOWLEDGEMENT', 'SESSION_ACKNOWLEDGEMENT_REMINDER', 'SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW', 'SESSION_ACKNOWLEDGED', 'SESSION_DISPUTED', 'PROGRESS_REPORT_SUBMITTED', 'ADMIN_NEW_TUTORING_REQUEST')")
