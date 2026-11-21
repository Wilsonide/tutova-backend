import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
    Boolean,
    JSON,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VerificationStatus(str, Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TutorVerification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_verifications"

    tutor_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(
            VerificationStatus,
            name="tutor_verification_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=VerificationStatus.NOT_SUBMITTED,
        nullable=False,
    )

    # Store private object-storage keys, not public document URLs.
    identity_document_key: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    # Actual uploaded file format, required to generate a secure download URL.
    identity_document_format: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    identity_document_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    nda_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    nda_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    introduction_video_key: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamp of the current approval decision. This is the start of the
    # tutor commission-tenure clock and is separate from the last review time.
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    review_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # A safeguarding flag blocks approval until an administrator records
    # an explicit safeguarding decision.
    safeguarding_review_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    safeguarding_review_reasons: Mapped[list] = mapped_column(
        JSON, default=list, nullable=False
    )
    safeguarding_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    safeguarding_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    safeguarding_review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
