import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.domain.tutors.models.tutor_profile import TutorProfile


class Subject(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(140),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    tutors: Mapped[list["TutorProfile"]] = relationship(
        "TutorProfile",
        secondary="tutor_subjects",
        back_populates="subjects",
    )


from app.domain.tutors.models.tutor_subject import tutor_subjects
