import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AgeGroup = Literal["PRIMARY", "SECONDARY", "ADULT"]
TutoringMode = Literal["ONLINE", "IN_PERSON", "HYBRID"]


class TutorProfileCreate(BaseModel):
    bio: str | None = Field(default=None, max_length=5000)
    monthly_fee: float | None = Field(default=None, gt=0, le=10000000)
    qualifications: str | None = Field(default=None, max_length=5000)

    years_of_experience: int = Field(default=0, ge=0, le=80)

    teaching_languages: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    learner_age_groups: list[AgeGroup] = Field(
        default_factory=list,
        max_length=3,
    )

    tutoring_modes: list[TutoringMode] = Field(
        default_factory=list,
        min_length=1,
        max_length=2,
    )

    service_area: str | None = Field(default=None, max_length=255)

    @field_validator("teaching_languages")
    @classmethod
    def validate_languages(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]

        if any(not value or len(value) > 100 for value in cleaned):
            raise ValueError("Each language must contain between 1 and 100 characters.")

        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("Duplicate languages are not allowed.")

        return cleaned

    @field_validator("learner_age_groups", "tutoring_modes")
    @classmethod
    def validate_unique_values(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Duplicate values are not allowed.")
        return values

    @field_validator("bio", "qualifications", "service_area")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TutorProfileUpdate(BaseModel):
    bio: str | None = Field(default=None, max_length=5000)
    monthly_fee: float | None = Field(default=None, gt=0, le=10000000)
    qualifications: str | None = Field(default=None, max_length=5000)

    years_of_experience: int | None = Field(
        default=None,
        ge=0,
        le=80,
    )

    teaching_languages: list[str] | None = Field(
        default=None,
        max_length=20,
    )

    learner_age_groups: list[AgeGroup] | None = Field(
        default=None,
        max_length=3,
    )

    tutoring_modes: list[TutoringMode] | None = Field(
        default=None,
        min_length=1,
        max_length=2,
    )

    service_area: str | None = Field(default=None, max_length=255)

    @field_validator("teaching_languages")
    @classmethod
    def validate_languages(
        cls,
        values: list[str] | None,
    ) -> list[str] | None:
        if values is None:
            return None

        cleaned = [value.strip() for value in values]

        if any(not value or len(value) > 100 for value in cleaned):
            raise ValueError("Each language must contain between 1 and 100 characters.")

        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("Duplicate languages are not allowed.")

        return cleaned

    @field_validator("learner_age_groups", "tutoring_modes")
    @classmethod
    def validate_unique_values(
        cls,
        values: list[str] | None,
    ) -> list[str] | None:
        if values is not None and len(set(values)) != len(values):
            raise ValueError("Duplicate values are not allowed.")
        return values

    @field_validator("bio", "qualifications", "service_area")
    @classmethod
    def clean_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TutorProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    bio: str | None
    monthly_fee: float | None
    qualifications: str | None
    years_of_experience: int
    teaching_languages: list[str]
    learner_age_groups: list[str]
    tutoring_modes: list[str]
    subject_ids: list[uuid.UUID] = Field(default_factory=list)
    location_ids: list[uuid.UUID] = Field(default_factory=list)
    profile_picture_url: str | None = None
    service_area: str | None
    created_at: datetime
    updated_at: datetime


class TutorProfilePictureResponse(BaseModel):
    message: str
    profile_picture_url: str


class TutorMediaDeleteResponse(BaseModel):
    message: str


class IdentityDocumentUploadResponse(BaseModel):
    message: str
    identity_document_type: str


class IdentityDocumentDownloadResponse(BaseModel):
    download_url: str
    expires_in_seconds: int


class TutorVideoUploadSignatureResponse(BaseModel):
    cloud_name: str
    api_key: str
    timestamp: int
    signature: str
    public_id: str


class TutorVideoUploadCompleteRequest(BaseModel):
    public_id: str = Field(min_length=1, max_length=500)
