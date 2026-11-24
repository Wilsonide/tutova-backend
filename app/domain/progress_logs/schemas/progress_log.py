import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.progress_logs.models.progress_log_entry import (
    ProgressLogEntryType,
    ProgressLogReviewStatus,
)


class ProgressLogCreate(BaseModel):
    entry_type: ProgressLogEntryType = ProgressLogEntryType.UPDATE
    message: str = Field(min_length=2, max_length=5000)


class ProgressLogReview(BaseModel):
    review_status: ProgressLogReviewStatus
    admin_review_notes: str | None = Field(default=None, max_length=5000)


class ProgressLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutoring_request_id: uuid.UUID
    author_user_id: uuid.UUID
    author_type: str
    author_name: str
    entry_type: ProgressLogEntryType
    log_date: date
    message: str
    review_status: ProgressLogReviewStatus
    admin_reviewed_by_user_id: uuid.UUID | None
    admin_reviewed_at: datetime | None
    admin_review_notes: str | None
    created_at: datetime
    updated_at: datetime



class ProgressLogRoomResponse(BaseModel):
    id: uuid.UUID
    status: str
    assigned_tutor_id: uuid.UUID
    created_at: datetime
    tutor_name: str
    requester_name: str
    requester_role: str
    learner_name: str | None = None
    subject_name: str
    tutoring_mode: str
