import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MatchingTutorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tutor_user_id: uuid.UUID
    tutor_profile_id: uuid.UUID | None = None
    response_decision: str | None = None

    first_name: str
    last_name: str

    bio: str | None = None
    monthly_fee: Decimal | None = None
    qualifications: str | None = None
    years_of_experience: int

    teaching_languages: list[str]
    learner_age_groups: list[str]
    tutoring_modes: list[str]
    service_area: str | None = None

    subjects: list[str]
    locations: list[str]

    match_level: Literal["STRONG", "PARTIAL"]
    match_reasons: list[str]
    unmatched_criteria: list[str]
