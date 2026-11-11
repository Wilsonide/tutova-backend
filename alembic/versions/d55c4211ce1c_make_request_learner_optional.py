"""make_request_learner_optional

Revision ID: d55c4211ce1c
Revises: 4cd02cf7d055
Create Date: 2026-11-11 00:02:27.341789
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d55c4211ce1c"
down_revision: Union[str, None] = "4cd02cf7d055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "tutoring_requests",
        "learner_profile_id",
        existing_type=None,
        nullable=True,
    )


def downgrade() -> None:
    # Existing parent requests may have NULL learner_profile_id values.
    # They must be resolved before this migration can be reversed.
    op.alter_column(
        "tutoring_requests",
        "learner_profile_id",
        existing_type=None,
        nullable=False,
    )
    # ### end Alembic commands ###
