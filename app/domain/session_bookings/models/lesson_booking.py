import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BookingStatus(str, enum.Enum):
    # New learner-initiated booking workflow.
    PENDING_TUTOR_CONFIRMATION = "PENDING_TUTOR_CONFIRMATION"

    # Legacy status retained for existing bookings during migration.
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"

    CONFIRMED = "CONFIRMED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    AWAITING_LEARNER_ACKNOWLEDGEMENT = "AWAITING_LEARNER_ACKNOWLEDGEMENT"
    DISPUTED = "DISPUTED"
    COMPLETED = "COMPLETED"


class LessonBooking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lesson_bookings"

    __table_args__ = (
        CheckConstraint(
            "duration_minutes >= 30 AND duration_minutes <= 240",
            name="ck_lesson_booking_duration",
        ),
        Index(
            "ix_lesson_booking_tutor_start",
            "tutor_profile_id",
            "start_at",
        ),
        Index(
            "ix_lesson_booking_requester_start",
            "requester_user_id",
            "start_at",
        ),
    )

    tutoring_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tutoring_requests.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    tutor_profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tutor_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Immutable pricing snapshot captured when the learner requests
    # the booking, using the tutor.s current monthly fee.
    monthly_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    gross_amount_minor: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="NGN",
        nullable=False,
    )

    status: Mapped[BookingStatus] = mapped_column(
        Enum(
            BookingStatus,
            name="booking_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=BookingStatus.PENDING_TUTOR_CONFIRMATION,
        nullable=False,
        index=True,
    )

    meeting_link: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
    )

    lesson_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    tutor_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    learner_acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    acknowledgement_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    acknowledgement_reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    admin_review_required_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    monthly_arrangement_id: Mapped[uuid.UUID | None] = mapped_column(
    Uuid(as_uuid=True),
    ForeignKey("monthly_tutoring_arrangements.id", ondelete="RESTRICT"),
    nullable=True,
    index=True,
)

    admin_review_notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    admin_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    admin_reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    admin_review_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    disputed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    dispute_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tutoring_request = relationship("TutoringRequest")
    tutor_profile = relationship("TutorProfile")
    requester = relationship(
        "User",
        foreign_keys=[requester_user_id],
    )
    location = relationship("Location")
    monthly_arrangement = relationship(
    "MonthlyTutoringArrangement",
    back_populates="lessons",
)
