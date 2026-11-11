import enum
import uuid

from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy import (
    ForeignKey,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TutorResponseDecision(str, enum.Enum):
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class TutorRequestResponse(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "tutor_request_responses"

    __table_args__ = (
        UniqueConstraint(
            "tutoring_request_id",
            "tutor_profile_id",
            name="uq_tutor_request_response_request_tutor",
        ),
    )

    tutoring_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tutoring_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tutor_profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tutor_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    decision: Mapped[TutorResponseDecision] = mapped_column(
        SAEnum(
            TutorResponseDecision,
            name="tutor_response_decision_enum",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )

    tutoring_request = relationship("TutoringRequest")
    tutor = relationship("TutorProfile")
