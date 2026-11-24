"""add indexes for notification and booking list/conflict queries

Revision ID: 0c91e7b4a632
Revises: d8f4a1c9b2e7
Create Date: 2026-11-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0c91e7b4a632"
down_revision = "d8f4a1c9b2e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_notifications_user_created_at",
        "notifications",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_lesson_booking_active_tutor_window",
        "lesson_bookings",
        ["tutor_profile_id", "start_at", "end_at"],
        unique=False,
        postgresql_where=sa.text(
            "status IN ('PENDING_TUTOR_CONFIRMATION', 'PENDING_CONFIRMATION', 'CONFIRMED')"
        ),
    )
    op.create_index(
        "ix_lesson_booking_active_requester_window",
        "lesson_bookings",
        ["requester_user_id", "start_at", "end_at"],
        unique=False,
        postgresql_where=sa.text(
            "status IN ('PENDING_TUTOR_CONFIRMATION', 'PENDING_CONFIRMATION', 'CONFIRMED')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lesson_booking_active_requester_window",
        table_name="lesson_bookings",
    )
    op.drop_index(
        "ix_lesson_booking_active_tutor_window",
        table_name="lesson_bookings",
    )
    op.drop_index(
        "ix_notifications_user_created_at",
        table_name="notifications",
    )
