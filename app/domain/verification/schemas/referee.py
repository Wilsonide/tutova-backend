from __future__ import annotations

from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.domain.verification.models.tutor_referee import RefereeStatus

Relationship = Literal[
    "Former or current employer / line manager",
    "Colleague or fellow educator",
    "School administrator / principal",
    "Academic supervisor / lecturer",
    "Community or religious leader",
    "Character reference",
    "Other",
]

KnownDuration = Literal[
    "Less than 1 year",
    "1 – 3 years",
    "3 – 5 years",
    "More than 5 years",
]

Rating = Literal["EXCELLENT", "GOOD", "FAIR", "POOR", "UNABLE_TO_JUDGE"]


class RefereeReferenceForm(BaseModel):
    """Validated answers to the Tutova safeguarding reference form."""

    relationship: Relationship
    relationship_other: str | None = Field(default=None, max_length=160)
    duration_known: KnownDuration
    observed_capacity: str | None = Field(default=None, max_length=2000)

    reliability: Rating
    patience_empathy: Rating
    communication: Rating
    honesty_integrity: Rating
    professionalism: Rating

    strengths: str | None = Field(default=None, max_length=3000)

    safeguarding_concern: Literal["NO", "YES"]
    misconduct_history: Literal["NO", "YES", "NOT_APPLICABLE"]
    safeguarding_details: str | None = Field(default=None, max_length=5000)

    recommendation: Literal[
        "YES_WITHOUT_RESERVATION",
        "YES_WITH_MINOR_RESERVATIONS",
        "NO",
    ]

    declaration: Literal[True]
    phone_number: str = Field(min_length=7, max_length=30)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        cleaned = value.strip()
        digits = sum(character.isdigit() for character in cleaned)
        if digits < 7:
            raise ValueError("Enter a valid phone number with at least 7 digits.")
        if not all(character.isdigit() or character in "+-() ." for character in cleaned):
            raise ValueError("Phone number contains unsupported characters.")
        return cleaned

    @field_validator(
        "relationship_other",
        "observed_capacity",
        "strengths",
        "safeguarding_details",
    )
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_other_relationship(self) -> "RefereeReferenceForm":
        if self.relationship == "Other" and not self.relationship_other:
            raise ValueError("Specify the relationship when selecting Other.")
        return self

    @property
    def requires_safeguarding_review(self) -> bool:
        return (
            self.safeguarding_concern == "YES"
            or self.misconduct_history == "YES"
            or any(
                rating == "POOR"
                for rating in (
                    self.reliability,
                    self.patience_empathy,
                    self.communication,
                    self.honesty_integrity,
                    self.professionalism,
                )
            )
        )

    @property
    def safeguarding_review_reasons(self) -> list[str]:
        reasons: list[str] = []
        if self.safeguarding_concern == "YES":
            reasons.append("REFEREE_RAISED_CHILD_SUITABILITY_CONCERN")
        if self.misconduct_history == "YES":
            reasons.append("REFEREE_REPORTED_MISCONDUCT_OR_CHILD_SAFETY_HISTORY")
        poor_ratings = [
            field
            for field in (
                "reliability",
                "patience_empathy",
                "communication",
                "honesty_integrity",
                "professionalism",
            )
            if getattr(self, field) == "POOR"
        ]
        if poor_ratings:
            reasons.append("POOR_REFERENCE_RATING:" + ",".join(poor_ratings))
        return reasons


class RefereeInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    job_title: str = Field(min_length=2, max_length=160)
    relationship_to_tutor: str = Field(min_length=2, max_length=100)


class TutorRefereeInviteRequest(BaseModel):
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
    reference_submitted_at: datetime | None = None


class AdminTutorRefereeResponse(TutorRefereeResponse):
    reference_response: dict | None = None
    reference_ip_address: str | None = None
    safeguarding_review_required: bool
    safeguarding_review_reasons: list[str]


class RefereeConsentPageResponse(BaseModel):
    referee_name: str
    referee_email: EmailStr
    tutor_name: str
    status: RefereeStatus
    token_expires_at: datetime


class RefereeConsentSubmission(BaseModel):
    consented_name: str = Field(min_length=2, max_length=160)
    consent: Literal[True]
    reference_form: RefereeReferenceForm

    @field_validator("consented_name")
    @classmethod
    def strip_consented_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter your full name.")
        return value


class SafeguardingReviewRequest(BaseModel):
    decision: Literal["CLEAR", "KEEP_FLAGGED"]
    review_notes: str = Field(min_length=5, max_length=3000)

    @field_validator("review_notes")
    @classmethod
    def strip_review_notes(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Safeguarding review notes are required.")
        return value
