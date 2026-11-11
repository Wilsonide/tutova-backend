import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.domain.parents.models.parent_profile import ParentProfile


class LearnerProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "learner_profiles"

    __table_args__ = (
        CheckConstraint(
            """
            (
                parent_profile_id IS NOT NULL
                AND user_id IS NULL
            )
            OR
            (
                parent_profile_id IS NULL
                AND user_id IS NOT NULL
            )
            """,
            name="ck_learner_profile_owner",
        ),
    )

    parent_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("parent_profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Used only when the learner has an independent adult account.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=True,
        index=True,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    parent: Mapped["ParentProfile | None"] = relationship(
        "ParentProfile",
        back_populates="learners",
    )
