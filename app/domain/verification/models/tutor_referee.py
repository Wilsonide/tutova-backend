import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
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
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    job_title: Mapped[str] = mapped_column(String(160), nullable=False)
    relationship_to_tutor: Mapped[str] = mapped_column(String(100), nullable=False)
    consent_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invitation_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RefereeStatus] = mapped_column(
        Enum(RefereeStatus, name="tutor_referee_status", values_callable=lambda e: [x.value for x in e]),
        default=RefereeStatus.PENDING, nullable=False, index=True,
    )
    consented_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    consent_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tutor = relationship("User", foreign_keys=[tutor_user_id])
