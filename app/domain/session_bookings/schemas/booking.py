import uuid
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.domain.session_bookings.models.lesson_booking import BookingStatus


class BookingCreate(BaseModel):
    """
    Created by a parent or adult learner to request a lesson session.
    The booking remains pending until the assigned tutor responds.
    """

    start_at: datetime
    duration_minutes: int = Field(ge=30, le=240)
    meeting_link: str | None = Field(default=None, max_length=1000)
    lesson_notes: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def validate_start_time(self):
        if self.start_at.tzinfo is None or self.start_at.utcoffset() is None:
            raise ValueError("start_at must include a timezone.")

        return self


class BookingDecline(BaseModel):
    """Optional reason supplied by the tutor when declining a request."""

    reason: str | None = Field(default=None, max_length=1000)


class BookingCancel(BaseModel):
    """Reason supplied by a participant when cancelling a booking."""

    reason: str = Field(min_length=3, max_length=1000)


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutoring_request_id: uuid.UUID
    tutor_profile_id: uuid.UUID
    requester_user_id: uuid.UUID

    start_at: datetime
    end_at: datetime
    duration_minutes: int

    hourly_rate: float | None = None
    gross_amount_minor: int | None = None
    currency: str = "NGN"

    status: BookingStatus

    meeting_link: str | None
    location_id: uuid.UUID | None
    lesson_notes: str | None

    cancellation_reason: str | None

    confirmed_at: datetime | None
    cancelled_at: datetime | None
    completed_at: datetime | None

    created_at: datetime
    updated_at: datetime

    tutor_completed_at: datetime | None
    learner_acknowledged_at: datetime | None

    disputed_at: datetime | None
    dispute_reason: str | None

    acknowledgement_deadline_at: datetime | None
    acknowledgement_reminder_sent_at: datetime | None

    admin_review_required_at: datetime | None
    admin_reviewed_at: datetime | None
    admin_reviewed_by_user_id: uuid.UUID | None
    admin_review_notes: str | None


class BookingDispute(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


class BookingAccept(BaseModel):
    """Optional meeting link supplied by the tutor when accepting."""

    meeting_link: str | None = Field(default=None, max_length=1000)
