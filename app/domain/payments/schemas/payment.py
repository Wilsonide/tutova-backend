import uuid
from decimal import Decimal
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.domain.payments.models.payment import PaymentStatus


class PaymentCheckoutResponse(BaseModel):
    payment_id: uuid.UUID
    booking_id: uuid.UUID
    checkout_url: str
    provider_reference: str
    amount_minor: int
    currency: str
    commission_bps: int
    platform_fee_minor: int
    tutor_earning_minor: int
    status: PaymentStatus


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID | None
    monthly_arrangement_id: uuid.UUID | None = None
    requester_user_id: uuid.UUID
    tutor_profile_id: uuid.UUID
    provider: str
    provider_reference: str
    checkout_url: str | None = None
    amount_minor: int
    currency: str
    commission_bps: int
    platform_fee_minor: int
    tutor_earning_minor: int
    tutor_completed_months_at_payment: Decimal
    status: PaymentStatus
    paid_at: datetime | None
    created_at: datetime

from pydantic import Field
from app.domain.payments.models.payout import PayoutStatus, RefundStatus


class PayoutRecipientCreate(BaseModel):
    account_name: str = Field(min_length=2, max_length=160)
    account_number: str = Field(min_length=8, max_length=12, pattern=r"^\d{8,12}$")
    bank_code: str = Field(min_length=2, max_length=12)


class PayoutRecipientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    bank_name: str
    account_name: str
    account_last4: str
    currency: str
    is_active: bool


class PayoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tutor_profile_id: uuid.UUID
    payment_id: uuid.UUID
    earning_period_start: date | None = None
    earning_period_end: date | None = None
    provider_reference: str
    amount_minor: int
    currency: str
    status: PayoutStatus
    failure_reason: str | None
    paid_at: datetime | None
    created_at: datetime


class RefundCreate(BaseModel):
    amount_minor: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=500)


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    payment_id: uuid.UUID
    provider_reference: str
    amount_minor: int
    tutor_share_minor: int
    platform_share_minor: int
    currency: str
    status: RefundStatus
    reason: str
    failure_reason: str | None
    processed_at: datetime | None
    created_at: datetime


class PayoutEligibleResponse(BaseModel):
    payment_id: uuid.UUID
    booking_id: uuid.UUID | None
    earning_period_start: date | None = None
    earning_period_end: date | None = None
    gross_amount_minor: int
    available_amount_minor: int
    currency: str
    paid_at: datetime | None


class TutorEarningsSummary(BaseModel):
    currency: str
    total_contract_amount_minor: int
    total_platform_commission_minor: int
    total_tutor_earnings_minor: int
    current_month_earnings_minor: int
    paid_out_minor: int
    held_tutor_earnings_minor: int
