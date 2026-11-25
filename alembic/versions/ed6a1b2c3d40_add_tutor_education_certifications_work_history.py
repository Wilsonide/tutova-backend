"""Add tutor education, institution suggestions, certifications and work history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "ed6a1b2c3d40"
down_revision = ("c6f2a9d1e840", "0c91e7b4a632")
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="APPROVED"),
        sa.Column("suggested_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_institutions_name", "institutions", ["name"])
    op.create_index("ix_institutions_country_code", "institutions", ["country_code"])
    op.create_index("ix_institutions_status", "institutions", ["status"])
    for table, extra in (
        ("tutor_education", [sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True), sa.Column("institution_name", sa.String(255), nullable=False), sa.Column("country_code", sa.String(2), nullable=False), sa.Column("course_of_study", sa.String(255), nullable=False), sa.Column("specialty", sa.String(255)), sa.Column("qualification_type", sa.String(80), nullable=False), sa.Column("grade", sa.String(100)), sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date()), sa.Column("currently_enrolled", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("document_public_id", sa.String(500)), sa.Column("document_name", sa.String(255)), sa.Column("document_format", sa.String(10))]),
        ("tutor_certifications", [sa.Column("name", sa.String(255), nullable=False), sa.Column("issuing_organization", sa.String(255)), sa.Column("date_obtained", sa.Date()), sa.Column("expiry_date", sa.Date()), sa.Column("document_public_id", sa.String(500)), sa.Column("document_name", sa.String(255)), sa.Column("document_format", sa.String(10))]),
        ("tutor_work_history", [sa.Column("organization", sa.String(255), nullable=False), sa.Column("job_title", sa.String(255), nullable=False), sa.Column("employment_type", sa.String(80)), sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date()), sa.Column("currently_working", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("description", sa.Text())]),
    ):
        op.create_table(table,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tutor_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tutor_profiles.id", ondelete="CASCADE"), nullable=False),
            *extra,
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index(f"ix_{table}_tutor_profile_id", table, ["tutor_profile_id"])

def downgrade() -> None:
    for table in ("tutor_work_history", "tutor_certifications", "tutor_education"):
        op.drop_index(f"ix_{table}_tutor_profile_id", table_name=table)
        op.drop_table(table)
    for name in ("status", "country_code", "name"):
        op.drop_index(f"ix_institutions_{name}", table_name="institutions")
    op.drop_table("institutions")
