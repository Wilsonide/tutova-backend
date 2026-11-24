import uuid
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.domain.agreements.models.tutoring_agreement import AgreementStatus

class AgreementChangeRequest(BaseModel):
    start_at: datetime
    duration_minutes: int = Field(ge=30, le=240)
    meeting_link: str | None = Field(default=None, max_length=1000)
    location_id: uuid.UUID | None = None
    lesson_notes: str | None = Field(default=None, max_length=3000)
    notes: str = Field(min_length=5, max_length=3000)

class AgreementLearnerDecision(BaseModel):
    decision: str = Field(pattern=r"^(ACCEPT|CANCEL)$")
    notes: str | None = Field(default=None, max_length=3000)

class AgreementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    booking_id: uuid.UUID
    tutoring_request_id: uuid.UUID
    requester_user_id: uuid.UUID
    tutor_profile_id: uuid.UUID
    status: AgreementStatus
    revision: int
    terms: dict
    revision_history: list
    tutor_reviewed_at: datetime | None
    learner_accepted_at: datetime | None
    tutor_notes: str | None
    learner_notes: str | None
    created_at: datetime
    updated_at: datetime
    tutor_name: str | None = None
    requester_name: str | None = None
    learner_name: str | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    venue: str | None = None
