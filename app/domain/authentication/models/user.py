import enum
import uuid

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    PARENT = "PARENT"
    ADULT_LEARNER = "ADULT_LEARNER"
    TUTOR = "TUTOR"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"


class AccountType(str, enum.Enum):
    PARENT = "PARENT"
    ADULT_LEARNER = "ADULT_LEARNER"
    TUTOR = "TUTOR"
    ADMIN = "ADMIN"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    phone_number: Mapped[str | None] = mapped_column(
        String(30), unique=True, index=True, nullable=True
    )

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False),
        nullable=False,
        index=True,
    )

    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, native_enum=False),
        nullable=False,
    )

    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False),
        default=UserStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    is_phone_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
