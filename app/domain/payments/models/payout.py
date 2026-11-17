import enum
import uuid
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PayoutStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class RefundStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class PayoutRecipient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payout_recipients"
    tutor_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tutor_profiles.id", ondelete="CASCADE"), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="PAYSTACK", nullable=False)
    recipient_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_name: Mapped[str] = mapped_column(String(160), nullable=False)
    account_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    tutor_profile = relationship("TutorProfile")


class TutorPayout(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tutor_payouts"
    __table_args__ = (
        Index("ix_tutor_payouts_tutor_created", "tutor_profile_id", "created_at"),
        UniqueConstraint(
            "payment_id", "earning_period_start",
            name="uq_tutor_payout_payment_earning_period",
        ),
    )
    tutor_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tutor_profiles.id", ondelete="RESTRICT"), nullable=False)
    payment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False)
    earning_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    earning_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    recipient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("payout_recipients.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="PAYSTACK", nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    transfer_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    status: Mapped[PayoutStatus] = mapped_column(Enum(PayoutStatus, name="payout_status", values_callable=lambda e: [x.value for x in e]), default=PayoutStatus.REQUESTED, nullable=False, index=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tutor_profile = relationship("TutorProfile")
    payment = relationship("Payment")
    recipient = relationship("PayoutRecipient")


class PaymentRefund(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_refunds"
    __table_args__ = (Index("ix_payment_refunds_payment_created", "payment_id", "created_at"),)
    payment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="PAYSTACK", nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    tutor_share_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_share_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    status: Mapped[RefundStatus] = mapped_column(Enum(RefundStatus, name="refund_status", values_callable=lambda e: [x.value for x in e]), default=RefundStatus.PENDING, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment = relationship("Payment")
    requested_by = relationship("User")
