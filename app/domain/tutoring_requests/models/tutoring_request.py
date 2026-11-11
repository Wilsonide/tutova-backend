import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TutoringMode(str, enum.Enum):
    ONLINE = "ONLINE"
    IN_PERSON = "IN_PERSON"


class TutoringRequestStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    CANCELLED = "CANCELLED"


class TutoringRequest(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "tutoring_requests"

    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Parents can create requests without a child learner profile.
    # Adult learners are automatically associated with their own profile.
    learner_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learner_profiles.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subjects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    tutoring_mode: Mapped[TutoringMode] = mapped_column(
        SAEnum(
            TutoringMode,
            name="tutoring_mode_enum",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    preferred_schedule: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[TutoringRequestStatus] = mapped_column(
        SAEnum(
            TutoringRequestStatus,
            name="tutoring_request_status_enum",
            native_enum=False,
            create_constraint=True,
        ),
        default=TutoringRequestStatus.OPEN,
        nullable=False,
        index=True,
    )

    # Optional tutor selected by the requester.
    # This is not the assigned tutor until the tutor accepts.
    selected_tutor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tutor_profiles.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Set only after a tutor accepts the request.
    assigned_tutor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tutor_profiles.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    requester = relationship(
        "User",
        foreign_keys=[requester_user_id],
    )

    learner = relationship("LearnerProfile")

    subject = relationship("Subject")

    location = relationship("Location")

    selected_tutor = relationship(
        "TutorProfile",
        foreign_keys=[selected_tutor_id],
    )

    assigned_tutor = relationship(
        "TutorProfile",
        foreign_keys=[assigned_tutor_id],
    )
