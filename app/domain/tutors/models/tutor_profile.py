import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.domain.locations.models.location import Location
    from app.domain.subjects.models.subject import Subject


class TutorProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tutor's agreed monthly tutoring fee in NGN. Payments are stored in kobo.
    monthly_fee: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    qualifications: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # Cloudinary public image asset ID. Never store the delivery URL.
    profile_picture_key: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    years_of_experience: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    teaching_languages: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    learner_age_groups: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    tutoring_modes: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    service_area: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    subjects: Mapped[list["Subject"]] = relationship(
        "Subject",
        secondary="tutor_subjects",
        back_populates="tutors",
    )

    locations: Mapped[list["Location"]] = relationship(
        "Location",
        secondary="tutor_locations",
        back_populates="tutors",
    )

    user = relationship("User")


from app.domain.tutors.models.tutor_location import tutor_locations
from app.domain.tutors.models.tutor_subject import tutor_subjects
