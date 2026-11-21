"""support hybrid tutoring requests

Revision ID: a4d91c6e8b20
Revises: 9a7c2d1e4f60
Create Date: 2026-11-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4d91c6e8b20"
down_revision: Union[str, None] = "9a7c2d1e4f60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "tutoring_mode_enum",
        "tutoring_requests",
        type_="check",
    )
    op.create_check_constraint(
        "tutoring_mode_enum",
        "tutoring_requests",
        "tutoring_mode IN ('ONLINE', 'IN_PERSON', 'HYBRID')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE tutoring_requests "
        "SET tutoring_mode = 'IN_PERSON' "
        "WHERE tutoring_mode = 'HYBRID'"
    )
    op.drop_constraint(
        "tutoring_mode_enum",
        "tutoring_requests",
        type_="check",
    )
    op.create_check_constraint(
        "tutoring_mode_enum",
        "tutoring_requests",
        "tutoring_mode IN ('ONLINE', 'IN_PERSON')",
    )
