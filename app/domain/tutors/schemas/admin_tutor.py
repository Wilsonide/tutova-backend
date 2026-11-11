import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.authentication.models.user import (
    AccountType,
    UserRole,
    UserStatus,
)
from app.domain.verification.models.tutor_verification import VerificationStatus


class AdminTutorProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    bio: str | None
    hourly_rate: Decimal | None
    qualifications: str | None
    years_of_experience: int
    teaching_languages: list[str]
    learner_age_groups: list[str]
    tutoring_modes: list[str]
    service_area: str | None
    profile_picture_url: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminTutorResponse(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone_number: str | None
    role: UserRole
    account_type: AccountType
    status: UserStatus
    is_email_verified: bool
    is_phone_verified: bool
    must_change_password: bool
    created_at: datetime

    verification_status: VerificationStatus | None = None
    tutor_profile: AdminTutorProfileResponse | None = None


class AdminTutorListResponse(BaseModel):
    items: list[AdminTutorResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class AdminTutorStatusUpdate(BaseModel):
    status: UserStatus = Field(...)
