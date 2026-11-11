import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.domain.learners.models.learner_profile import LearnerProfile


class ParentProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "parent_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    learners: Mapped[list["LearnerProfile"]] = relationship(
        "LearnerProfile",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
