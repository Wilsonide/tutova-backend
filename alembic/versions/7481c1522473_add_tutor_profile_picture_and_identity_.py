"""add tutor profile picture and identity document format

Revision ID: 7481c1522473
Revises: 1a3bda1cf4d5
Create Date: 2026-11-10 15:34:12.487585
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "7481c1522473"
down_revision: Union[str, None] = "1a3bda1cf4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tutor_profiles",
        sa.Column(
            "profile_picture_key",
            sa.String(length=500),
            nullable=True,
        ),
    )

    op.add_column(
        "tutor_verifications",
        sa.Column(
            "identity_document_format",
            sa.String(length=20),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "tutor_verifications",
        "identity_document_format",
    )

    op.drop_column(
        "tutor_profiles",
        "profile_picture_key",
    )
