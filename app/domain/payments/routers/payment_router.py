import uuid
from datetime import date

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.dependencies import (
    CurrentUser,
    DBSession,
    RequireBookingAdmin,
    RequireTutor,
)
from app.domain.payments.models.payment import Payment
from app.domain.payments.models.payout import (
    PaymentRefund,
    PayoutRecipient,
    TutorPayout,
)
from app.domain.payments.schemas.payment import (
    PaymentCheckoutResponse,
    PaymentResponse,
    PayoutEligibleResponse,
    PayoutRecipientCreate,
    PayoutRecipientResponse,
    PayoutResponse,
    RefundCreate,
    RefundResponse,
    TutorEarningsSummary,
)
from app.domain.payments.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "/bookings/{booking_id}/initialize",
    response_model=PaymentCheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def initialize_booking_payment(
    booking_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    payment = await PaymentService(db).initialize_booking_payment(
        current_user, booking_id, idempotency_key
    )
    return PaymentCheckoutResponse(
        payment_id=payment.id,
        booking_id=payment.booking_id,
        checkout_url=payment.checkout_url,
        provider_reference=payment.provider_reference,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        commission_bps=payment.commission_bps,
        platform_fee_minor=payment.platform_fee_minor,
        tutor_earning_minor=payment.tutor_earning_minor,
        status=payment.status,
    )


@router.get("/mine", response_model=list[PaymentResponse])
async def list_my_payments(current_user: CurrentUser, db: DBSession):
    return await PaymentService(db).list_for_user(current_user)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def paystack_webhook(request: Request, db: DBSession):
    await PaymentService(db).handle_webhook(
        await request.body(), request.headers.get("x-paystack-signature")
    )
    return {"success": True}


@router.post("/reference/{reference}/verify", response_model=PaymentResponse)
async def verify_payment_reference(
    reference: str, current_user: CurrentUser, db: DBSession
):
    service = PaymentService(db)
    payment = await db.scalar(
        select(Payment).where(Payment.provider_reference == reference)
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    if not any(
        item.id == payment.id for item in await service.list_for_user(current_user)
    ):
        raise HTTPException(status_code=403, detail="You cannot verify this payment.")
    return await service.verify_reference(reference)


# Tutor payout destination. Raw bank account number is sent to Paystack and is not stored by Tutova.
@router.put("/payout-destination", response_model=PayoutRecipientResponse)
async def set_payout_destination(
    payload: PayoutRecipientCreate, current_user: RequireTutor, db: DBSession
):
    return await PaymentService(db).save_payout_recipient(
        current_user, **payload.model_dump()
    )


@router.get("/payout-destination", response_model=PayoutRecipientResponse)
async def get_payout_destination(current_user: RequireTutor, db: DBSession):
    from app.domain.tutors.models.tutor_profile import TutorProfile

    tutor_id = await db.scalar(
        select(TutorProfile.id).where(TutorProfile.user_id == current_user.id)
    )
    recipient = await db.scalar(
        select(PayoutRecipient).where(
            PayoutRecipient.tutor_profile_id == tutor_id,
            PayoutRecipient.is_active.is_(True),
        )
    )
    if recipient is None:
        raise HTTPException(
            status_code=404, detail="No payout destination has been configured."
        )
    return recipient


@router.post(
    "/payouts/request/{payment_id}",
    response_model=PayoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_tutor_payout(
    payment_id: uuid.UUID,
    current_user: RequireTutor,
    db: DBSession,
    earning_period_start: date | None = Query(default=None),
):
    return await PaymentService(db).request_payout(
        current_user, payment_id, earning_period_start=earning_period_start
    )


@router.get("/payouts/eligible", response_model=list[PayoutEligibleResponse])
async def list_eligible_payouts(current_user: RequireTutor, db: DBSession):
    return await PaymentService(db).list_eligible_payouts(current_user)


@router.get("/earnings/summary", response_model=TutorEarningsSummary)
async def get_tutor_earnings_summary(current_user: RequireTutor, db: DBSession):
    return await PaymentService(db).get_earnings_summary(current_user)


@router.get("/payouts/mine", response_model=list[PayoutResponse])
async def list_my_payouts(current_user: RequireTutor, db: DBSession):
    return await PaymentService(db).list_payouts_for_user(current_user)


@router.get("/admin/payouts", response_model=list[PayoutResponse])
async def list_all_payouts(_: RequireBookingAdmin, db: DBSession):
    return await PaymentService(db).list_all_payouts()


@router.post("/admin/payouts/{payout_id}/process", response_model=PayoutResponse)
async def process_tutor_payout(
    payout_id: uuid.UUID, _: RequireBookingAdmin, db: DBSession
):
    return await PaymentService(db).process_payout(payout_id)


@router.post("/admin/payouts/{payout_id}/retry", response_model=PayoutResponse)
async def retry_tutor_payout(
    payout_id: uuid.UUID, _: RequireBookingAdmin, db: DBSession
):
    return await PaymentService(db).retry_payout(payout_id)


class PayoutOtpPayload(BaseModel):
    otp: str = Field(min_length=4, max_length=12)


@router.post("/admin/payouts/{payout_id}/finalize", response_model=PayoutResponse)
async def finalize_tutor_payout(
    payout_id: uuid.UUID,
    payload: PayoutOtpPayload,
    _: RequireBookingAdmin,
    db: DBSession,
):
    return await PaymentService(db).finalize_payout(payout_id, payload.otp)


@router.post("/admin/payouts/{payout_id}/verify", response_model=PayoutResponse)
async def verify_tutor_payout(
    payout_id: uuid.UUID, _: RequireBookingAdmin, db: DBSession
):
    return await PaymentService(db).verify_payout(payout_id)


@router.post(
    "/admin/{payment_id}/refund",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
)
async def initiate_refund(
    payment_id: uuid.UUID,
    payload: RefundCreate,
    current_user: RequireBookingAdmin,
    db: DBSession,
):
    return await PaymentService(db).request_refund(
        current_user, payment_id, payload.amount_minor, payload.reason
    )


@router.get("/admin/refunds", response_model=list[RefundResponse])
async def list_all_refunds(_: RequireBookingAdmin, db: DBSession):
    return await PaymentService(db).list_all_refunds()


@router.post("/admin/refunds/{refund_id}/verify", response_model=RefundResponse)
async def verify_refund(refund_id: uuid.UUID, _: RequireBookingAdmin, db: DBSession):
    return await PaymentService(db).verify_refund(refund_id)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    payment = await db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    visible = await PaymentService(db).list_for_user(current_user)
    if not any(item.id == payment.id for item in visible):
        raise HTTPException(status_code=403, detail="You cannot access this payment.")
    return payment
