import uuid
from sqlalchemy import Boolean, Date, ForeignKey, String, Text, Uuid, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class Institution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "institutions"
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="APPROVED", nullable=False, index=True)
    suggested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

class TutorEducation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_education"
    tutor_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tutor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True)
    institution_name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    course_of_study: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qualification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[object] = mapped_column(Date, nullable=False)
    end_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    currently_enrolled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    document_public_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_format: Mapped[str | None] = mapped_column(String(10), nullable=True)

class TutorCertification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_certifications"
    tutor_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tutor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuing_organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_obtained: Mapped[object | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    document_public_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_format: Mapped[str | None] = mapped_column(String(10), nullable=True)

class TutorWorkHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_work_history"
    tutor_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tutor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    organization: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    employment_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    start_date: Mapped[object] = mapped_column(Date, nullable=False)
    end_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    currently_working: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class TutorOnboardingDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_onboarding_drafts"
    __table_args__ = (
        UniqueConstraint("tutor_user_id", name="uq_tutor_onboarding_drafts_user"),
    )
    tutor_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
