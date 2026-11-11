import uuid

from pydantic import BaseModel, ConfigDict, Field


class PublicSubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class PublicLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    location_type: str


class PublicTutorResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID

    first_name: str
    last_name: str
    full_name: str

    bio: str | None
    qualifications: str | None
    years_of_experience: int

    hourly_rate: float | None

    teaching_languages: list[str]
    learner_age_groups: list[str]
    tutoring_modes: list[str]
    profile_picture_url: str | None = None

    service_area: str | None

    subjects: list[PublicSubjectResponse]
    locations: list[PublicLocationResponse]

    introduction_video_url: str | None


class PublicTutorListResponse(BaseModel):
    items: list[PublicTutorResponse]

    page: int
    per_page: int
    total: int
    total_pages: int


class TutorVideoUploadResponse(BaseModel):
    message: str
    introduction_video_url: str
