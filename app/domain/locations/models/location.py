import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.domain.tutors.models.tutor_profile import TutorProfile


from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LocationType(str, Enum):
    STATE = "STATE"
    CITY = "CITY"
    LGA = "LGA"
    NEIGHBORHOOD = "NEIGHBORHOOD"


class Location(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(180),
        unique=True,
        nullable=False,
        index=True,
    )

    location_type: Mapped[LocationType] = mapped_column(
        SAEnum(
            LocationType,
            name="location_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    country_code: Mapped[str] = mapped_column(
        String(2),
        default="NG",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    parent: Mapped["Location | None"] = relationship(
        "Location",
        remote_side="Location.id",
        back_populates="children",
    )

    children: Mapped[list["Location"]] = relationship(
        "Location",
        back_populates="parent",
    )

    tutors: Mapped[list["TutorProfile"]] = relationship(
        "TutorProfile",
        secondary="tutor_locations",
        back_populates="locations",
    )
