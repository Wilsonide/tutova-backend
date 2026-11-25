from datetime import date
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, model_validator

class InstitutionSuggestion(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    country_code: str = Field(min_length=2, max_length=2)

class EducationItem(BaseModel):
    id: UUID | None = None
    institution_id: UUID | None = None
    institution_name: str = Field(min_length=2, max_length=255)
    country_code: str = Field(min_length=2, max_length=2)
    course_of_study: str = Field(min_length=2, max_length=255)
    specialty: str | None = Field(default=None, max_length=255)
    qualification_type: str = Field(min_length=2, max_length=80)
    grade: str | None = Field(default=None, max_length=100)
    start_date: date
    end_date: date | None = None
    currently_enrolled: bool = False
    document_public_id: str | None = Field(default=None, max_length=500)
    document_name: str | None = Field(default=None, max_length=255)
    document_format: str | None = Field(default=None, max_length=10)
    @model_validator(mode="after")
    def dates_valid(self):
        if self.currently_enrolled and self.end_date is not None:
            raise ValueError("End date must be empty while currently enrolled.")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date.")
        return self

class CertificationItem(BaseModel):
    id: UUID | None = None
    name: str = Field(min_length=2, max_length=255)
    issuing_organization: str | None = Field(default=None, max_length=255)
    date_obtained: date | None = None
    expiry_date: date | None = None
    document_public_id: str | None = Field(default=None, max_length=500)
    document_name: str | None = Field(default=None, max_length=255)
    document_format: str | None = Field(default=None, max_length=10)

class WorkHistoryItem(BaseModel):
    id: UUID | None = None
    organization: str = Field(min_length=2, max_length=255)
    job_title: str = Field(min_length=2, max_length=255)
    employment_type: str | None = Field(default=None, max_length=80)
    start_date: date
    end_date: date | None = None
    currently_working: bool = False
    description: str | None = Field(default=None, max_length=3000)
    @model_validator(mode="after")
    def dates_valid(self):
        if self.currently_working and self.end_date is not None:
            raise ValueError("End date must be empty while currently working.")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date.")
        return self

class BackgroundReplace(BaseModel):
    education: list[EducationItem] = Field(default_factory=list, max_length=20)
    certifications: list[CertificationItem] = Field(default_factory=list, max_length=30)
    work_history: list[WorkHistoryItem] = Field(default_factory=list, max_length=30)

class BackgroundResponse(BaseModel):
    education: list[dict]
    certifications: list[dict]
    work_history: list[dict]
