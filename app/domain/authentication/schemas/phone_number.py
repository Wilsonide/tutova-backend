from pydantic import BaseModel, Field, field_validator


class PhoneNumberUpdateRequest(BaseModel):
    phone_number: str | None = Field(max_length=30)

    @field_validator("phone_number")
    @classmethod
    def clean_phone_number(cls, value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()

        if not cleaned:
            return None

        if len(cleaned) < 7:
            raise ValueError("Enter a valid phone number.")

        return cleaned
