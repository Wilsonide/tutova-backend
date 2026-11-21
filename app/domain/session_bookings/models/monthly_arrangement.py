
import enum
import uuid
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    JSON,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MonthlyArrangementStatus(str, enum.Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class MonthlyTutoringArrangement(
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "monthly_tutoring_arrangements"

    __table_args__ = (
        CheckConstraint(
            "monthly_fee_minor > 0",
            name="ck_monthly_arrangement_fee_positive",
        ),
        CheckConstraint(
            "period_end >= period_start",
            name="ck_monthly_arrangement_period",
        ),
        CheckConstraint(
            "duration_months >= 1 AND duration_months <= 3",
            name="ck_monthly_arrangement_duration",
        ),
        CheckConstraint(
            "commission_bps >= 0 AND commission_bps <= 10000",
            name="ck_monthly_arrangement_commission",
        ),
        CheckConstraint(
            "platform_fee_minor >= 0 AND tutor_earning_minor > 0",
            name="ck_monthly_arrangement_earnings",
        ),
        UniqueConstraint(
            "tutoring_request_id",
            "period_start",
            name="uq_monthly_arrangement_request_period",
        ),
        Index(
            "ix_monthly_arrangement_requester_period",
            "requester_user_id",
            "period_start",
        ),
        Index(
            "ix_monthly_arrangement_tutor_period",
            "tutor_profile_id",
            "period_start",
        ),
        Index(
            "ix_monthly_arrangement_status_period",
            "status",
            "period_end",
        ),
    )

    tutoring_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tutoring_requests.id", ondelete="RESTRICT"),
        nullable=False,
    )

    tutor_profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tutor_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )

    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Immutable monthly price snapshot, stored in the smallest currency unit.
    monthly_fee_minor: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Contract duration is fixed to 1, 2, or 3 calendar months.
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Immutable commission and tutor earnings snapshots captured when the
    # tutoring arrangement is created.
    commission_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    # Aggregate immutable snapshots across all contract months.
    platform_fee_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    tutor_commission_minor: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    learner_fee_minor: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    tutor_earning_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    # Per-month snapshots allow the commission tier to change during a contract.
    commission_schedule: Mapped[list[dict]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    completed_months_at_creation: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="NGN",
        nullable=False,
    )

    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[MonthlyArrangementStatus] = mapped_column(
        Enum(
            MonthlyArrangementStatus,
            name="monthly_arrangement_status",
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        default=MonthlyArrangementStatus.PENDING_PAYMENT,
        nullable=False,
        index=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    tutoring_request = relationship("TutoringRequest")
    tutor_profile = relationship("TutorProfile")
    requester = relationship("User", foreign_keys=[requester_user_id])

    lessons = relationship(
        "LessonBooking",
        back_populates="monthly_arrangement",
    )

    payments = relationship(
        "Payment",
        back_populates="monthly_arrangement",
    )
