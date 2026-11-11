import enum
import uuid
from decimal import Decimal
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_requester_created", "requester_user_id", "created_at"),
        Index("ix_payments_tutor_created", "tutor_profile_id", "created_at"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lesson_bookings.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    tutor_profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tutor_profiles.id", ondelete="RESTRICT"), nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(30), default="PAYSTACK", nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    checkout_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    commission_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_fee_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    tutor_earning_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    tutor_completed_hours_at_payment: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", values_callable=lambda e: [x.value for x in e]),
        default=PaymentStatus.PENDING, nullable=False, index=True,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    booking = relationship("LessonBooking")
    requester = relationship("User", foreign_keys=[requester_user_id])
    tutor_profile = relationship("TutorProfile")
