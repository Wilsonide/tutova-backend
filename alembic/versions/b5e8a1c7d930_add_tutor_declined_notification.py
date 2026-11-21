"""add selected tutor declined notification

Revision ID: b5e8a1c7d930
Revises: a4d91c6e8b20
Create Date: 2026-11-21
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b5e8a1c7d930"
down_revision: Union[str, None] = "a4d91c6e8b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOTIFICATION_TYPES = (
    "'NEW_MATCHING_REQUEST', 'TUTOR_ACCEPTED_REQUEST', "
    "'TUTOR_DECLINED_REQUEST', 'BOOKING_REQUEST_RECEIVED', "
    "'BOOKING_ACCEPTED', 'BOOKING_DECLINED', 'BOOKING_PAYMENT_CONFIRMED', "
    "'SESSION_AWAITING_ACKNOWLEDGEMENT', 'SESSION_ACKNOWLEDGEMENT_REMINDER', "
    "'SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW', 'SESSION_ACKNOWLEDGED', "
    "'SESSION_DISPUTED', 'PROGRESS_REPORT_SUBMITTED', "
    "'ADMIN_NEW_TUTORING_REQUEST', 'AGREEMENT_READY_FOR_TUTOR', "
    "'AGREEMENT_READY_FOR_LEARNER', 'AGREEMENT_SIGNED'"
)


def upgrade() -> None:
    op.drop_constraint("notification_type_enum", "notifications", type_="check")
    op.create_check_constraint(
        "notification_type_enum",
        "notifications",
        f"notification_type IN ({NOTIFICATION_TYPES})",
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM notifications "
        "WHERE notification_type = 'TUTOR_DECLINED_REQUEST'"
    )
    op.drop_constraint("notification_type_enum", "notifications", type_="check")
    op.create_check_constraint(
        "notification_type_enum",
        "notifications",
        "notification_type IN ("
        "'NEW_MATCHING_REQUEST', 'TUTOR_ACCEPTED_REQUEST', "
        "'BOOKING_REQUEST_RECEIVED', 'BOOKING_ACCEPTED', 'BOOKING_DECLINED', "
        "'BOOKING_PAYMENT_CONFIRMED', 'SESSION_AWAITING_ACKNOWLEDGEMENT', "
        "'SESSION_ACKNOWLEDGEMENT_REMINDER', "
        "'SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW', "
        "'SESSION_ACKNOWLEDGED', 'SESSION_DISPUTED', "
        "'PROGRESS_REPORT_SUBMITTED', 'ADMIN_NEW_TUTORING_REQUEST', "
        "'AGREEMENT_READY_FOR_TUTOR', 'AGREEMENT_READY_FOR_LEARNER', "
        "'AGREEMENT_SIGNED'"
        ")",
    )
