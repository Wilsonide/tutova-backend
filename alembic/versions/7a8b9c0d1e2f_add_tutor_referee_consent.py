"""add tutor referee invitations and consent tracking

Revision ID: 7a8b9c0d1e2f
Revises: df47a8b12c60
Create Date: 2026-11-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7a8b9c0d1e2f"
down_revision: Union[str, None] = "df47a8b12c60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    referee_status = postgresql.ENUM(
        "PENDING", "CONSENTED", "DECLINED", "EXPIRED",
        name="tutor_referee_status",
        create_type=False,
    )
    referee_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "tutor_referees",
        sa.Column("tutor_user_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("relationship_to_tutor", sa.String(length=100), nullable=False),
        sa.Column("consent_token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invitation_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", referee_status, server_default="PENDING", nullable=False),
        sa.Column("consented_name", sa.String(length=160), nullable=True),
        sa.Column("consent_statement", sa.Text(), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tutor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tutor_user_id", "email", name="uq_tutor_referee_tutor_email"),
        sa.UniqueConstraint("consent_token_hash"),
    )
    op.create_index("ix_tutor_referees_tutor_status", "tutor_referees", ["tutor_user_id", "status"])
    op.create_index("ix_tutor_referees_status", "tutor_referees", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tutor_referees_status", table_name="tutor_referees")
    op.drop_index("ix_tutor_referees_tutor_status", table_name="tutor_referees")
    op.drop_table("tutor_referees")
    postgresql.ENUM(
        name="tutor_referee_status", create_type=False
    ).drop(op.get_bind(), checkfirst=True)
