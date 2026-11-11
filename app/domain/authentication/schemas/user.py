import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.domain.authentication.models.user import (
    AccountType,
    UserRole,
    UserStatus,
)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
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
