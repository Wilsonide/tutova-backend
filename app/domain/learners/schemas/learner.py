import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LearnerProfileCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class LearnerProfileUpdate(BaseModel):
    first_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    last_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class LearnerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_profile_id: uuid.UUID | None
    user_id: uuid.UUID | None
    first_name: str
    last_name: str
    created_at: datetime
    updated_at: datetime
