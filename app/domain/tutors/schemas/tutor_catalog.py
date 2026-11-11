import uuid

from pydantic import BaseModel, Field


class TutorCatalogSelection(BaseModel):
    subject_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    location_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
