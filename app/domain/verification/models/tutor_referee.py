import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RefereeStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONSENTED = "CONSENTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class TutorReferee(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_referees"
    __table_args__ = (
        UniqueConstraint("tutor_user_id", "email", name="uq_tutor_referee_tutor_email"),
        Index("ix_tutor_referees_tutor_status", "tutor_user_id", "status"),
    )

    tutor_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Links a replacement invitation to the prior referee record without
    # overwriting any previously submitted consent/reference response.
    supersedes_referee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tutor_referees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    job_title: Mapped[str] = mapped_column(String(160), nullable=False)
    relationship_to_tutor: Mapped[str] = mapped_column(String(100), nullable=False)
    consent_token_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    token_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    invitation_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[RefereeStatus] = mapped_column(
        Enum(
            RefereeStatus,
            name="tutor_referee_status",
            values_callable=lambda e: [x.value for x in e],
        ),
        default=RefereeStatus.PENDING,
        nullable=False,
        index=True,
    )
    consented_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    consent_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Full structured safeguarding reference response. Kept private from tutors.
    reference_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reference_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reference_ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    safeguarding_review_required: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    safeguarding_review_reasons: Mapped[list] = mapped_column(
        JSON, default=list, nullable=False
    )

    tutor = relationship("User", foreign_keys=[tutor_user_id])
