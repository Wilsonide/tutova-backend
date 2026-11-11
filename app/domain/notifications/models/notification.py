import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationType(str, enum.Enum):
    NEW_MATCHING_REQUEST = "NEW_MATCHING_REQUEST"
    TUTOR_ACCEPTED_REQUEST = "TUTOR_ACCEPTED_REQUEST"

    BOOKING_REQUEST_RECEIVED = "BOOKING_REQUEST_RECEIVED"
    BOOKING_ACCEPTED = "BOOKING_ACCEPTED"
    BOOKING_DECLINED = "BOOKING_DECLINED"

    SESSION_AWAITING_ACKNOWLEDGEMENT = "SESSION_AWAITING_ACKNOWLEDGEMENT"
    SESSION_ACKNOWLEDGEMENT_REMINDER = "SESSION_ACKNOWLEDGEMENT_REMINDER"
    SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW = (
        "SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW"
    )
    SESSION_ACKNOWLEDGED = "SESSION_ACKNOWLEDGED"
    SESSION_DISPUTED = "SESSION_DISPUTED"


class Notification(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    notification_type: Mapped[NotificationType] = mapped_column(
        SAEnum(
            NotificationType,
            name="notification_type_enum",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # Store identifiers and navigation metadata, not private learner details.
    data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user = relationship("User")
