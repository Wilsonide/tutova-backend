import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProgressReportAuthor(str, enum.Enum):
    TUTOR = "TUTOR"
    LEARNER = "LEARNER"


class ProgressReportReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FLAGGED = "FLAGGED"
    RESOLVED = "RESOLVED"


class ProgressReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "progress_reports"
    __table_args__ = (
        UniqueConstraint("booking_id", "author_user_id", name="uq_progress_report_booking_author"),
        Index("ix_progress_reports_booking_created", "booking_id", "created_at"),
        Index("ix_progress_reports_review_status", "review_status", "created_at"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lesson_bookings.id", ondelete="CASCADE"), nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    author_type: Mapped[ProgressReportAuthor] = mapped_column(Enum(ProgressReportAuthor, name="progress_report_author", native_enum=False, create_constraint=True), nullable=False)
    lesson_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    topic_covered: Mapped[str] = mapped_column(String(500), nullable=False)
    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    activities: Mapped[str | None] = mapped_column(Text, nullable=True)
    learner_performance: Mapped[str | None] = mapped_column(Text, nullable=True)
    challenges: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    attendance_confirmed: Mapped[bool] = mapped_column(nullable=False)
    satisfaction_rating: Mapped[int | None] = mapped_column(nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    issue_reported: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    issue_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[ProgressReportReviewStatus] = mapped_column(Enum(ProgressReportReviewStatus, name="progress_report_review_status", native_enum=False, create_constraint=True), default=ProgressReportReviewStatus.PENDING, nullable=False, index=True)
    admin_reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    booking = relationship("LessonBooking")
    author = relationship("User", foreign_keys=[author_user_id])
    admin_reviewer = relationship("User", foreign_keys=[admin_reviewed_by_user_id])
