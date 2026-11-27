"""Preserve prior referee responses when an invitation is replaced."""

from alembic import op
import sqlalchemy as sa

revision = "a6c9e2f41b70"
down_revision = "f2a6c9d1e840"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tutor_referees",
        sa.Column("supersedes_referee_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_tutor_referees_supersedes_referee_id",
        "tutor_referees",
        ["supersedes_referee_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_tutor_referees_supersedes_referee_id_tutor_referees",
        "tutor_referees",
        "tutor_referees",
        ["supersedes_referee_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tutor_referees_supersedes_referee_id_tutor_referees",
        "tutor_referees",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_tutor_referees_supersedes_referee_id",
        table_name="tutor_referees",
    )
    op.drop_column("tutor_referees", "supersedes_referee_id")
