import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProgressLogEntryType(str, enum.Enum):
    UPDATE = "UPDATE"
    QUESTION = "QUESTION"
    MILESTONE = "MILESTONE"
    CONCERN = "CONCERN"


class ProgressLogReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"
    FLAGGED = "FLAGGED"
    RESOLVED = "RESOLVED"


class ProgressLogEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "progress_log_entries"
    __table_args__ = (
        Index("ix_progress_log_request_created", "tutoring_request_id", "created_at"),
        Index("ix_progress_log_review_created", "review_status", "created_at"),
        Index("ix_progress_log_author_created", "author_user_id", "created_at"),
    )

    tutoring_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tutoring_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    author_type: Mapped[str] = mapped_column(
        Enum("TUTOR", "LEARNER", name="progress_log_author_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    entry_type: Mapped[ProgressLogEntryType] = mapped_column(
        Enum(
            ProgressLogEntryType,
            name="progress_log_entry_type",
            native_enum=False,
            create_constraint=True,
        ),
        default=ProgressLogEntryType.UPDATE,
        nullable=False,
    )
    log_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[ProgressLogReviewStatus] = mapped_column(
        Enum(
            ProgressLogReviewStatus,
            name="progress_log_review_status",
            native_enum=False,
            create_constraint=True,
        ),
        default=ProgressLogReviewStatus.PENDING,
        nullable=False,
        index=True,
    )
    admin_reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    admin_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tutoring_request = relationship("TutoringRequest")
    author = relationship("User", foreign_keys=[author_user_id])
    admin_reviewer = relationship("User", foreign_keys=[admin_reviewed_by_user_id])

    @property
    def author_name(self) -> str:
        if self.author is None:
            return "Tutova member"
        return f"{self.author.first_name} {self.author.last_name}".strip()
