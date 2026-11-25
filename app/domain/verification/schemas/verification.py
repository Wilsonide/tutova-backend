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
    nda_content: str | None = None
    nda_accepted_ip: str | None = None
    nda_accepted_user_agent: str | None = None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    review_notes: str | None


class AdminVerificationResponse(VerificationStatusResponse):
    tutor_user_id: uuid.UUID
    identity_document_type: str | None
    introduction_video_url: str | None = None
    safeguarding_review_required: bool
    safeguarding_review_reasons: list[str]
    safeguarding_reviewed_by: uuid.UUID | None
    safeguarding_reviewed_at: datetime | None
    safeguarding_review_notes: str | None


class VerificationReviewRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "CHANGES_REQUESTED"]
    review_notes: str | None = Field(default=None, max_length=3000)



class NdaAcceptanceRequest(BaseModel):
    version: str = Field(min_length=1, max_length=50)
