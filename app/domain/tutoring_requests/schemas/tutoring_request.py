import uuid
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.domain.tutoring_requests.models.tutor_request_response import (
    TutorResponseDecision,
)
from app.domain.tutoring_requests.models.tutoring_request import (
    TutoringMode,
    TutoringRequestStatus,
)


class TutoringRequestCreate(BaseModel):
    # Optional for backward compatibility.
    # The service resolves the actual learner association from the user role.
    learner_profile_id: uuid.UUID | None = None

    subject_id: uuid.UUID
    location_id: uuid.UUID | None = None
    tutoring_mode: TutoringMode

    description: str = Field(
        min_length=10,
        max_length=5000,
    )

    preferred_schedule: str | None = Field(
        default=None,
        max_length=500,
    )

    # Optional user ID of the tutor selected from tutor discovery.
    # If omitted, the request is broadcast to matching tutors.
    selected_tutor_user_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_location(self):
        if self.tutoring_mode in {TutoringMode.IN_PERSON, TutoringMode.HYBRID} and self.location_id is None:
            raise ValueError("A location is required for in-person or hybrid tutoring.")

        return self


class TutoringRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_user_id: uuid.UUID

    # Parent requests have no child learner profile association.
    learner_profile_id: uuid.UUID | None

    subject_id: uuid.UUID
    location_id: uuid.UUID | None

    tutoring_mode: TutoringMode
    description: str
    preferred_schedule: str | None

    status: TutoringRequestStatus

    # The selected tutor and accepted tutor are intentionally separate.
    selected_tutor_id: uuid.UUID | None
    assigned_tutor_id: uuid.UUID | None
    selected_tutor_response: str | None = None

    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TutorRequestDecision(BaseModel):
    decision: str = Field(
        pattern=r"^(ACCEPT|DECLINE)$",
    )


class TutorMatchingRequestResponse(BaseModel):
    """
    Restricted information shown to an eligible matching tutor.

    Requester contact details and internal account identifiers
    are intentionally excluded.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

    # Requester details
    requester_first_name: str
    requester_last_name: str
    requester_account_type: str | None = None

    # Request details
    subject_id: uuid.UUID
    subject_name: str

    location_id: uuid.UUID | None
    location_name: str | None = None

    tutoring_mode: TutoringMode
    description: str
    preferred_schedule: str | None
    created_at: datetime
    status: TutoringRequestStatus
    selected_tutor_id: uuid.UUID | None = None
    assigned_tutor_id: uuid.UUID | None = None
    my_response: str | None = None


class TutorRequestDecisionResult(BaseModel):
    request_id: uuid.UUID
    decision: TutorResponseDecision
    request_status: TutoringRequestStatus
    message: str
