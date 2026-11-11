"""add booking notification types

Revision ID: a710420e305e
Revises: 12558887b120
Create Date: 2026-11-11 12:59:11.481307
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a710420e305e"
down_revision: Union[str, None] = "12558887b120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "notification_type_enum",
        "notifications",
        type_="check",
    )

    op.create_check_constraint(
        "notification_type_enum",
        "notifications",
        """
        notification_type IN (
            'NEW_MATCHING_REQUEST',
            'TUTOR_ACCEPTED_REQUEST',
            'BOOKING_REQUEST_RECEIVED',
            'BOOKING_ACCEPTED',
            'BOOKING_DECLINED',
            'SESSION_AWAITING_ACKNOWLEDGEMENT',
            'SESSION_ACKNOWLEDGEMENT_REMINDER',
            'SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW',
            'SESSION_ACKNOWLEDGED',
            'SESSION_DISPUTED'
        )
        """,
    )


def downgrade() -> None:
    op.drop_constraint(
        "notification_type_enum",
        "notifications",
        type_="check",
    )

    op.create_check_constraint(
        "notification_type_enum",
        "notifications",
        """
        notification_type IN (
            'NEW_MATCHING_REQUEST',
            'TUTOR_ACCEPTED_REQUEST',
            'SESSION_AWAITING_ACKNOWLEDGEMENT',
            'SESSION_ACKNOWLEDGEMENT_REMINDER',
            'SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW',
            'SESSION_ACKNOWLEDGED',
            'SESSION_DISPUTED'
        )
        """,
    )
