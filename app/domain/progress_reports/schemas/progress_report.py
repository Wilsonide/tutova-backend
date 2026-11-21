import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.domain.progress_reports.models.progress_report import ProgressReportAuthor, ProgressReportReviewStatus


class ProgressReportCreate(BaseModel):
    lesson_date: datetime
    topic_covered: str = Field(min_length=2, max_length=500)
    learning_objectives: str | None = Field(default=None, max_length=5000)
    activities: str | None = Field(default=None, max_length=5000)
    learner_performance: str | None = Field(default=None, max_length=5000)
    challenges: str | None = Field(default=None, max_length=5000)
    next_steps: str | None = Field(default=None, max_length=5000)
    attendance_confirmed: bool
    satisfaction_rating: int | None = Field(default=None, ge=1, le=5)
    feedback: str | None = Field(default=None, max_length=5000)
    issue_reported: bool = False
    issue_details: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_issue(self):
        if self.issue_reported and not (self.issue_details or self.feedback):
            raise ValueError("Provide details when reporting an issue.")
        return self


class ProgressReportReview(BaseModel):
    review_status: ProgressReportReviewStatus
    admin_review_notes: str | None = Field(default=None, max_length=5000)


class ProgressReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    booking_id: uuid.UUID
    author_user_id: uuid.UUID
    author_type: ProgressReportAuthor
    lesson_date: datetime
    topic_covered: str
    learning_objectives: str | None
    activities: str | None
    learner_performance: str | None
    challenges: str | None
    next_steps: str | None
    attendance_confirmed: bool
    satisfaction_rating: int | None
    feedback: str | None
    issue_reported: bool
    issue_details: str | None
    review_status: ProgressReportReviewStatus
    admin_reviewed_by_user_id: uuid.UUID | None
    admin_reviewed_at: datetime | None
    admin_review_notes: str | None
    created_at: datetime
    updated_at: datetime
