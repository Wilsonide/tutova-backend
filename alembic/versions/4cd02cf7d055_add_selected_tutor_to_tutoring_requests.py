"""Add selected tutor to tutoring requests

Revision ID: 4cd02cf7d055
Revises: 7481c1522473
Create Date: 2026-11-10 23:16:05.995218
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "4cd02cf7d055"
down_revision: Union[str, None] = "7481c1522473"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tutoring_requests",
        sa.Column(
            "selected_tutor_id",
            sa.Uuid(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_tutoring_requests_selected_tutor_id_tutor_profiles",
        "tutoring_requests",
        "tutor_profiles",
        ["selected_tutor_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_tutoring_requests_selected_tutor_id",
        "tutoring_requests",
        ["selected_tutor_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tutoring_requests_selected_tutor_id",
        table_name="tutoring_requests",
    )

    op.drop_constraint(
        "fk_tutoring_requests_selected_tutor_id_tutor_profiles",
        "tutoring_requests",
        type_="foreignkey",
    )

    op.drop_column(
        "tutoring_requests",
        "selected_tutor_id",
    )
    # ### end Alembic commands ###
