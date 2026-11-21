import enum
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class AgreementStatus(str, enum.Enum):
    PENDING_TUTOR_REVIEW = "PENDING_TUTOR_REVIEW"
    PENDING_LEARNER_APPROVAL = "PENDING_LEARNER_APPROVAL"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    SIGNED = "SIGNED"
    CANCELLED = "CANCELLED"

class TutoringAgreement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutoring_agreements"
    booking_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lesson_bookings.id", ondelete="CASCADE"), unique=True, nullable=False)
    tutoring_request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tutoring_requests.id", ondelete="RESTRICT"), nullable=False, index=True)
    requester_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    tutor_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tutor_profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[AgreementStatus] = mapped_column(Enum(AgreementStatus, name="tutoring_agreement_status", native_enum=False, create_constraint=True), default=AgreementStatus.PENDING_TUTOR_REVIEW, nullable=False, index=True)
    revision: Mapped[int] = mapped_column(default=1, nullable=False)
    terms: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision_history: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tutor_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    learner_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tutor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    learner_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking = relationship("LessonBooking")
    tutoring_request = relationship("TutoringRequest")
    requester = relationship("User", foreign_keys=[requester_user_id])
    tutor = relationship("TutorProfile")
