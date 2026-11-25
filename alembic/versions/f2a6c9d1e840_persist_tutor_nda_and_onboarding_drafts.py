"""Persist tutor NDA acceptance evidence and onboarding drafts."""

from alembic import op
import sqlalchemy as sa

revision = "f2a6c9d1e840"
down_revision = "ed6a1b2c3d40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tutor_verifications", sa.Column("nda_content", sa.Text(), nullable=True))
    op.add_column("tutor_verifications", sa.Column("nda_accepted_ip", sa.String(length=45), nullable=True))
    op.add_column("tutor_verifications", sa.Column("nda_accepted_user_agent", sa.String(length=500), nullable=True))

    op.create_table(
        "tutor_onboarding_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tutor_user_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tutor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tutor_user_id", name="uq_tutor_onboarding_drafts_user"),
    )


def downgrade() -> None:
    op.drop_table("tutor_onboarding_drafts")
    op.drop_column("tutor_verifications", "nda_accepted_user_agent")
    op.drop_column("tutor_verifications", "nda_accepted_ip")
    op.drop_column("tutor_verifications", "nda_content")
