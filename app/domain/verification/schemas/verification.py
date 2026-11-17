import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.verification.models.tutor_verification import (
    VerificationStatus,
)

IdentityDocumentType = Literal[
    "NATIONAL_ID",
    "PASSPORT",
    "DRIVERS_LICENSE",
    "OTHER_APPROVED_ID",
]


class VerificationSubmission(BaseModel):
    identity_document_type: IdentityDocumentType
    accept_nda: bool


class VerificationStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: VerificationStatus
    nda_version: str | None
    nda_accepted_at: datetime | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    review_notes: str | None


class AdminVerificationResponse(VerificationStatusResponse):
    tutor_user_id: uuid.UUID
    identity_document_type: str | None


class VerificationReviewRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "CHANGES_REQUESTED"]
    review_notes: str | None = Field(default=None, max_length=3000)


from pydantic import EmailStr
from app.domain.verification.models.tutor_referee import RefereeStatus


class RefereeInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    job_title: str = Field(min_length=2, max_length=160)
    relationship_to_tutor: str = Field(min_length=2, max_length=100)


class TutorRefereeInviteRequest(BaseModel):
    # At least two referees are required. Tutors may provide additional referees.
    referees: list[RefereeInput] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_unique_referees(self):
        emails = [str(item.email).strip().lower() for item in self.referees]
        if len(set(emails)) != len(emails):
            raise ValueError("Each referee must have a different email address.")
        return self


class TutorRefereeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    job_title: str
    relationship_to_tutor: str
    status: RefereeStatus
    invitation_sent_at: datetime | None
    consented_at: datetime | None
    responded_at: datetime | None


class RefereeConsentPageResponse(BaseModel):
    referee_name: str
    referee_email: EmailStr
    tutor_name: str
    status: RefereeStatus
    token_expires_at: datetime


class RefereeConsentSubmission(BaseModel):
    consented_name: str = Field(min_length=2, max_length=160)
    consent: bool
