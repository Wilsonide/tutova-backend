import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.locations.models.location import LocationType


class LocationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(
        min_length=2,
        max_length=180,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    location_type: LocationType
    parent_id: uuid.UUID | None = None
    country_code: str = Field(default="NG", min_length=2, max_length=2)


class CommunityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    lga_id: uuid.UUID


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    location_type: LocationType
    parent_id: uuid.UUID | None
    country_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
