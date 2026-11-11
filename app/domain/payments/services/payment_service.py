import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.authentication.models.user import User
from app.domain.payments.models.payment import Payment, PaymentStatus
from app.domain.payments.paystack import PaystackError, PaystackProvider
from app.domain.session_bookings.models.lesson_booking import (
    BookingStatus,
    LessonBooking,
)
from app.domain.tutors.models.tutor_profile import TutorProfile


class PaymentService:
    def __init__(self, db: AsyncSession, provider: PaystackProvider | None = None):
        self.db = db
        self.provider = provider

    def _get_provider(self) -> PaystackProvider:
        if self.provider is None:
            self.provider = self._provider_from_settings()
        return self.provider

    @staticmethod
    def _provider_from_settings() -> PaystackProvider:
        if settings.PAYMENT_PROVIDER.upper() != "PAYSTACK":
            raise HTTPException(
                status_code=503, detail="Payment provider is not configured."
            )
        return PaystackProvider(
            settings.PAYSTACK_SECRET_KEY,
            base_url=settings.PAYSTACK_BASE_URL,
            callback_url=settings.PAYSTACK_CALLBACK_URL or None,
            timeout_seconds=settings.PAYSTACK_TIMEOUT_SECONDS,
            channels=tuple(settings.paystack_channels),
        )

    @staticmethod
    def _commission_bps(completed_hours: Decimal) -> int:
        # 0 hours = newly onboarded (25%); 0-50 completed hours = 20%;
        # more than 50 completed hours = 15%. Exactly 50 remains at 20%.
        if completed_hours <= 0:
            return 2500
        if completed_hours <= 50:
            return 2000
        return 1500

    async def initialize_booking_payment(
        self, user: User, booking_id: uuid.UUID, idempotency_key: str
    ) -> Payment:
        if not idempotency_key or len(idempotency_key) > 120:
            raise HTTPException(
                status_code=422, detail="A valid Idempotency-Key is required."
            )

        existing = await self.db.scalar(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        provider = self._get_provider()
        if existing:
            if (
                existing.booking_id != booking_id
                or existing.requester_user_id != user.id
            ):
                raise HTTPException(
                    status_code=409, detail="Idempotency key already used."
                )
            if existing.status == PaymentStatus.PAID:
                raise HTTPException(
                    status_code=409, detail="This booking has already been paid."
                )
            if existing.status == PaymentStatus.FAILED:
                raise HTTPException(
                    status_code=409,
                    detail="This payment attempt failed. Retry with a new Idempotency-Key.",
                )
            if existing.checkout_url:
                return existing
            # The provider may have accepted the first initialize request even if
            # the network response was lost. Retry with the same persisted reference.
            try:
                existing.checkout_url = await provider.initialize_payment(
                    reference=existing.provider_reference,
                    amount_minor=existing.amount_minor,
                    currency=existing.currency,
                    email=user.email,
                )
                await self.db.commit()
                await self.db.refresh(existing)
                return existing
            except Exception:
                await self.db.rollback()
                raise

        booking = await self.db.scalar(
            select(LessonBooking)
            .where(LessonBooking.id == booking_id)
            .with_for_update()
        )
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found.")
        if booking.requester_user_id != user.id:
            raise HTTPException(
                status_code=403, detail="Only the booking requester can pay."
            )
        if booking.status != BookingStatus.CONFIRMED:
            raise HTTPException(
                status_code=409, detail="Only confirmed bookings can be paid."
            )
        if booking.gross_amount_minor is None or booking.gross_amount_minor <= 0:
            raise HTTPException(
                status_code=409, detail="This booking has no valid price snapshot."
            )

        pending_payment = await self.db.scalar(
            select(Payment)
            .where(
                Payment.booking_id == booking.id,
                Payment.status == PaymentStatus.PENDING,
            )
            .order_by(Payment.created_at.desc())
        )
        if pending_payment is not None:
            raise HTTPException(
                status_code=409,
                detail=f"A payment is already awaiting completion. Retrieve payment {pending_payment.id} to reuse its checkout URL.",
            )

        already_paid = await self.db.scalar(
            select(Payment.id).where(
                Payment.booking_id == booking.id, Payment.status == PaymentStatus.PAID
            )
        )
        if already_paid:
            raise HTTPException(
                status_code=409, detail="This booking has already been paid."
            )

        tutor = await self.db.get(TutorProfile, booking.tutor_profile_id)
        if tutor is None:
            raise HTTPException(status_code=404, detail="Tutor profile not found.")

        completed_minutes = await self.db.scalar(
            select(func.coalesce(func.sum(LessonBooking.duration_minutes), 0)).where(
                LessonBooking.tutor_profile_id == tutor.id,
                LessonBooking.status == BookingStatus.COMPLETED,
                LessonBooking.learner_acknowledged_at.is_not(None),
            )
        )
        completed_hours = Decimal(completed_minutes or 0) / Decimal(60)
        commission_bps = self._commission_bps(completed_hours)
        gross = booking.gross_amount_minor
        platform_fee = (gross * commission_bps + 5000) // 10000
        tutor_earning = gross - platform_fee

        payment = Payment(
            booking_id=booking.id,
            requester_user_id=user.id,
            tutor_profile_id=tutor.id,
            provider=provider.name,
            provider_reference=f"tutova-{uuid.uuid4().hex}",
            idempotency_key=idempotency_key,
            amount_minor=gross,
            currency=booking.currency or "NGN",
            commission_bps=commission_bps,
            platform_fee_minor=platform_fee,
            tutor_earning_minor=tutor_earning,
            tutor_completed_hours_at_payment=completed_hours.quantize(Decimal("0.01")),
            status=PaymentStatus.PENDING,
        )
        self.db.add(payment)
        # Persist the internal reference before contacting Paystack. If the
        # provider response is lost, the same idempotency key can safely retry.
        await self.db.commit()
        await self.db.refresh(payment)
        try:
            payment.checkout_url = await provider.initialize_payment(
                reference=payment.provider_reference,
                amount_minor=payment.amount_minor,
                currency=payment.currency,
                email=user.email,
            )
            await self.db.commit()
            await self.db.refresh(payment)
            return payment
        except Exception:
            await self.db.rollback()
            raise

    async def verify_reference(self, reference: str) -> Payment:
        provider = self._get_provider()
        payment = await self.db.scalar(
            select(Payment)
            .where(Payment.provider_reference == reference)
            .with_for_update()
        )
        if payment is None:
            raise HTTPException(status_code=404, detail="Payment reference not found.")
        if payment.status == PaymentStatus.PAID:
            return payment
        try:
            verified = await provider.verify_payment(provider_reference=reference)
        except PaystackError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if (
            verified.provider != payment.provider
            or verified.provider_reference != payment.provider_reference
            or verified.amount_minor != payment.amount_minor
            or verified.currency.upper() != payment.currency.upper()
        ):
            raise HTTPException(
                status_code=409,
                detail="Verified payment does not match this transaction.",
            )
        if verified.status.upper() not in {"SUCCESS", "SUCCEEDED", "PAID"}:
            if verified.status.upper() in {"FAILED", "CANCELLED", "ABANDONED"}:
                payment.status = PaymentStatus.FAILED
                payment.failure_reason = f"Paystack reported {verified.status.upper()}"
                await self.db.commit()
            return payment
        payment.status = PaymentStatus.PAID
        payment.paid_at = datetime.now(timezone.utc)
        payment.failure_reason = None
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def handle_webhook(self, raw_body: bytes, signature: str | None) -> None:
        provider = self._get_provider()
        if not signature or not provider.verify_webhook_signature(
            raw_body=raw_body, signature=signature
        ):
            raise HTTPException(
                status_code=401, detail="Invalid payment webhook signature."
            )
        try:
            event = provider.parse_webhook(raw_body=raw_body)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid webhook payload."
            ) from exc
        if event.event_type == "charge.success":
            await self.verify_reference(event.provider_reference)
        elif event.event_type in {
            "transfer.success",
            "transfer.failed",
            "transfer.reversed",
        }:
            from app.domain.payments.models.payout import TutorPayout

            payout = await self.db.scalar(
                select(TutorPayout).where(
                    TutorPayout.provider_reference == event.provider_reference
                )
            )
            if payout is not None:
                await self.verify_payout(payout.id)
        elif event.event_type in {
            "refund.processed",
            "refund.failed",
            "refund.pending",
        }:
            from app.domain.payments.models.payout import PaymentRefund

            refund = await self.db.scalar(
                select(PaymentRefund).where(
                    PaymentRefund.provider_reference == event.provider_reference
                )
            )
            if refund is not None:
                await self.verify_refund(refund.id)

    async def list_for_user(self, user: User) -> list[Payment]:
        tutor_profile_id = await self.db.scalar(
            select(TutorProfile.id).where(TutorProfile.user_id == user.id)
        )
        query = select(Payment).where(Payment.requester_user_id == user.id)
        if tutor_profile_id:
            query = select(Payment).where(
                (Payment.requester_user_id == user.id)
                | (Payment.tutor_profile_id == tutor_profile_id)
            )
        return list(
            (await self.db.scalars(query.order_by(Payment.created_at.desc()))).all()
        )

    async def save_payout_recipient(
        self, user: User, *, account_name: str, account_number: str, bank_code: str
    ):
        from app.domain.payments.models.payout import PayoutRecipient

        tutor = await self.db.scalar(
            select(TutorProfile).where(TutorProfile.user_id == user.id)
        )
        if tutor is None:
            raise HTTPException(status_code=404, detail="Tutor profile not found.")
        provider = self._get_provider()
        try:
            details = await provider.create_transfer_recipient(
                name=account_name,
                account_number=account_number,
                bank_code=bank_code,
                currency="NGN",
            )
        except (PaystackError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        recipient = await self.db.scalar(
            select(PayoutRecipient)
            .where(PayoutRecipient.tutor_profile_id == tutor.id)
            .with_for_update()
        )
        if recipient is None:
            recipient = PayoutRecipient(
                tutor_profile_id=tutor.id,
                provider=provider.name,
                recipient_code=details["recipient_code"],
                bank_name=details["bank_name"],
                account_name=details["account_name"],
                account_last4=details["account_number"][-4:],
                currency="NGN",
            )
            self.db.add(recipient)
        else:
            recipient.provider = provider.name
            recipient.recipient_code = details["recipient_code"]
            recipient.bank_name = details["bank_name"]
            recipient.account_name = details["account_name"]
            recipient.account_last4 = details["account_number"][-4:]
            recipient.currency = "NGN"
            recipient.is_active = True
        await self.db.commit()
        await self.db.refresh(recipient)
        return recipient

    async def request_payout(self, user: User, payment_id: uuid.UUID):
        from app.domain.payments.models.payout import (
            PaymentRefund,
            PayoutRecipient,
            PayoutStatus,
            RefundStatus,
            TutorPayout,
        )

        tutor = await self.db.scalar(
            select(TutorProfile).where(TutorProfile.user_id == user.id)
        )
        if tutor is None:
            raise HTTPException(status_code=404, detail="Tutor profile not found.")
        payment = await self.db.scalar(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        )
        if payment is None or payment.tutor_profile_id != tutor.id:
            raise HTTPException(status_code=404, detail="Eligible payment not found.")
        if payment.status not in {PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED}:
            raise HTTPException(
                status_code=409,
                detail="Only successfully paid lessons can be paid out.",
            )
        booking = await self.db.get(LessonBooking, payment.booking_id)
        if (
            booking is None
            or booking.status != BookingStatus.COMPLETED
            or booking.learner_acknowledged_at is None
        ):
            raise HTTPException(
                status_code=409,
                detail="Tutor earnings become payable after lesson completion and learner acknowledgement.",
            )
        recipient = await self.db.scalar(
            select(PayoutRecipient).where(
                PayoutRecipient.tutor_profile_id == tutor.id,
                PayoutRecipient.is_active.is_(True),
            )
        )
        if recipient is None:
            raise HTTPException(
                status_code=409,
                detail="Add and verify a bank account before requesting payout.",
            )
        existing = await self.db.scalar(
            select(TutorPayout).where(TutorPayout.payment_id == payment.id)
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="A payout has already been requested for this lesson.",
            )
        refunds = list(
            (
                await self.db.scalars(
                    select(PaymentRefund).where(
                        PaymentRefund.payment_id == payment.id,
                        PaymentRefund.status != RefundStatus.FAILED,
                    )
                )
            ).all()
        )
        if any(
            refund.status in {RefundStatus.PENDING, RefundStatus.PROCESSING}
            for refund in refunds
        ):
            raise HTTPException(
                status_code=409, detail="A refund is being processed for this lesson."
            )
        refunded_tutor_share = sum(
            refund.tutor_share_minor
            for refund in refunds
            if refund.status == RefundStatus.PROCESSED
        )
        payable = payment.tutor_earning_minor - refunded_tutor_share
        if payable <= 0:
            raise HTTPException(
                status_code=409,
                detail="There are no tutor earnings available for this payment.",
            )
        payout = TutorPayout(
            tutor_profile_id=tutor.id,
            payment_id=payment.id,
            recipient_id=recipient.id,
            provider=payment.provider,
            provider_reference=f"tutova-payout-{uuid.uuid4().hex}",
            amount_minor=payable,
            currency=payment.currency,
            status=PayoutStatus.REQUESTED,
        )
        self.db.add(payout)
        await self.db.commit()
        await self.db.refresh(payout)
        return payout

    async def process_payout(self, payout_id: uuid.UUID):
        from app.domain.payments.models.payout import PayoutStatus, TutorPayout

        payout = await self.db.scalar(
            select(TutorPayout).where(TutorPayout.id == payout_id).with_for_update()
        )
        if payout is None:
            raise HTTPException(status_code=404, detail="Payout not found.")
        if payout.status != PayoutStatus.REQUESTED:
            raise HTTPException(
                status_code=409, detail="Only requested payouts can be processed."
            )
        from app.domain.payments.models.payout import PayoutRecipient

        recipient = await self.db.get(PayoutRecipient, payout.recipient_id)
        try:
            result = await self._get_provider().initiate_payout(
                reference=payout.provider_reference,
                amount_minor=payout.amount_minor,
                currency=payout.currency,
                destination_token=recipient.recipient_code,
            )
        except (PaystackError, ValueError) as exc:
            # A timeout can occur after Paystack accepted the transfer. Keep it
            # reserved and reconcile the same reference before any retry.
            payout.status = PayoutStatus.PROCESSING
            payout.failure_reason = (
                "Provider response uncertain; verify this reference before retrying."
            )
            await self.db.commit()
            raise HTTPException(
                status_code=502,
                detail="Payout submission is unconfirmed. Verify the payout reference before retrying.",
            ) from exc
        payout.transfer_code = result.transfer_code or payout.transfer_code
        normalized = result.status.upper()
        if normalized in {"SUCCESS", "SUCCESSFUL"}:
            payout.status = PayoutStatus.PAID
            payout.paid_at = datetime.now(timezone.utc)
        elif normalized in {"FAILED", "REVERSED"}:
            payout.status = PayoutStatus.FAILED
            payout.failure_reason = f"Paystack transfer status: {normalized}"
        else:
            payout.status = PayoutStatus.PROCESSING
        await self.db.commit()
        await self.db.refresh(payout)
        return payout

    async def retry_payout(self, payout_id: uuid.UUID):
        from app.domain.payments.models.payout import PayoutStatus, TutorPayout

        payout = await self.db.scalar(
            select(TutorPayout).where(TutorPayout.id == payout_id).with_for_update()
        )
        if payout is None:
            raise HTTPException(status_code=404, detail="Payout not found.")
        if payout.status not in {PayoutStatus.FAILED, PayoutStatus.REVERSED}:
            raise HTTPException(
                status_code=409,
                detail="Only failed or reversed payouts can be retried.",
            )
        payout.provider_reference = f"tutova-payout-{uuid.uuid4().hex}"
        payout.status = PayoutStatus.REQUESTED
        payout.failure_reason = None
        payout.paid_at = None
        await self.db.commit()
        await self.db.refresh(payout)
        return payout

    async def finalize_payout(self, payout_id: uuid.UUID, otp: str):
        from app.domain.payments.models.payout import PayoutStatus, TutorPayout

        payout = await self.db.scalar(
            select(TutorPayout).where(TutorPayout.id == payout_id).with_for_update()
        )
        if payout is None:
            raise HTTPException(status_code=404, detail="Payout not found.")
        if payout.status != PayoutStatus.PROCESSING or not payout.transfer_code:
            raise HTTPException(
                status_code=409,
                detail="This payout is not awaiting transfer OTP approval.",
            )
        try:
            result = await self._get_provider().finalize_payout(
                transfer_code=payout.transfer_code, otp=otp
            )
        except (PaystackError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail="Paystack could not finalize the transfer. Verify its status before retrying.",
            ) from exc
        if (
            result.provider_reference != payout.provider_reference
            or result.amount_minor != payout.amount_minor
        ):
            raise HTTPException(
                status_code=409,
                detail="Finalized transfer does not match the payout record.",
            )
        normalized = result.status.upper()
        if normalized in {"SUCCESS", "SUCCESSFUL"}:
            payout.status = PayoutStatus.PAID
            payout.paid_at = datetime.now(timezone.utc)
            payout.failure_reason = None
        elif normalized in {"FAILED", "REVERSED"}:
            payout.status = (
                PayoutStatus.FAILED if normalized == "FAILED" else PayoutStatus.REVERSED
            )
            payout.failure_reason = f"Paystack transfer status: {normalized}"
        else:
            payout.status = PayoutStatus.PROCESSING
        await self.db.commit()
        await self.db.refresh(payout)
        return payout

    async def verify_payout(self, payout_id: uuid.UUID):
        from app.domain.payments.models.payout import PayoutStatus, TutorPayout

        payout = await self.db.scalar(
            select(TutorPayout).where(TutorPayout.id == payout_id).with_for_update()
        )
        if payout is None:
            raise HTTPException(status_code=404, detail="Payout not found.")
        try:
            result = await self._get_provider().verify_payout(
                provider_reference=payout.provider_reference
            )
        except PaystackError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if (
            result.amount_minor != payout.amount_minor
            or result.currency.upper() != payout.currency.upper()
        ):
            raise HTTPException(
                status_code=409,
                detail="Verified payout does not match the recorded payout.",
            )
        status_value = result.status.upper()
        if status_value in {"SUCCESS", "SUCCESSFUL"}:
            payout.status = PayoutStatus.PAID
            payout.paid_at = payout.paid_at or datetime.now(timezone.utc)
            payout.failure_reason = None
        elif status_value in {"FAILED", "REVERSED"}:
            payout.status = (
                PayoutStatus.FAILED
                if status_value == "FAILED"
                else PayoutStatus.REVERSED
            )
            payout.failure_reason = f"Paystack transfer status: {status_value}"
        else:
            payout.status = PayoutStatus.PROCESSING
        await self.db.commit()
        await self.db.refresh(payout)
        return payout

    async def list_eligible_payouts(self, user: User):
        from app.domain.payments.models.payout import (
            PaymentRefund,
            PayoutRecipient,
            RefundStatus,
            TutorPayout,
        )

        tutor_id = await self.db.scalar(
            select(TutorProfile.id).where(TutorProfile.user_id == user.id)
        )
        if tutor_id is None:
            raise HTTPException(status_code=404, detail="Tutor profile not found.")
        payments = list(
            (
                await self.db.scalars(
                    select(Payment)
                    .join(LessonBooking, Payment.booking_id == LessonBooking.id)
                    .where(
                        Payment.tutor_profile_id == tutor_id,
                        Payment.status.in_(
                            [PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED]
                        ),
                        LessonBooking.status == BookingStatus.COMPLETED,
                        LessonBooking.learner_acknowledged_at.is_not(None),
                    )
                    .order_by(Payment.paid_at.asc())
                )
            ).all()
        )
        eligible = []
        for payment in payments:
            payout = await self.db.scalar(
                select(TutorPayout.id).where(TutorPayout.payment_id == payment.id)
            )
            if payout:
                continue
            refunds = list(
                (
                    await self.db.scalars(
                        select(PaymentRefund).where(
                            PaymentRefund.payment_id == payment.id,
                            PaymentRefund.status != RefundStatus.FAILED,
                        )
                    )
                ).all()
            )
            if any(
                item.status in {RefundStatus.PENDING, RefundStatus.PROCESSING}
                for item in refunds
            ):
                continue
            refunded_tutor_share = sum(
                item.tutor_share_minor
                for item in refunds
                if item.status == RefundStatus.PROCESSED
            )
            available = payment.tutor_earning_minor - refunded_tutor_share
            if available > 0:
                eligible.append(
                    {
                        "payment_id": payment.id,
                        "booking_id": payment.booking_id,
                        "gross_amount_minor": payment.amount_minor,
                        "available_amount_minor": available,
                        "currency": payment.currency,
                        "paid_at": payment.paid_at,
                    }
                )
        return eligible

    async def list_payouts_for_user(self, user: User):
        from app.domain.payments.models.payout import TutorPayout

        tutor_id = await self.db.scalar(
            select(TutorProfile.id).where(TutorProfile.user_id == user.id)
        )
        if tutor_id is None:
            return []
        return list(
            (
                await self.db.scalars(
                    select(TutorPayout)
                    .where(TutorPayout.tutor_profile_id == tutor_id)
                    .order_by(TutorPayout.created_at.desc())
                )
            ).all()
        )

    async def request_refund(
        self, admin: User, payment_id: uuid.UUID, amount_minor: int, reason: str
    ):
        from app.domain.payments.models.payout import (
            PaymentRefund,
            PayoutStatus,
            RefundStatus,
            TutorPayout,
        )

        payment = await self.db.scalar(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        )
        if payment is None:
            raise HTTPException(status_code=404, detail="Payment not found.")
        if payment.status not in {PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED}:
            raise HTTPException(
                status_code=409, detail="Only successful payments can be refunded."
            )
        payout = await self.db.scalar(
            select(TutorPayout).where(
                TutorPayout.payment_id == payment.id,
                TutorPayout.status.in_(
                    [PayoutStatus.REQUESTED, PayoutStatus.PROCESSING, PayoutStatus.PAID]
                ),
            )
        )
        if payout:
            raise HTTPException(
                status_code=409,
                detail="Refund is unavailable because tutor payout has already been requested or sent.",
            )
        previous = list(
            (
                await self.db.scalars(
                    select(PaymentRefund).where(
                        PaymentRefund.payment_id == payment.id,
                        PaymentRefund.status != RefundStatus.FAILED,
                    )
                )
            ).all()
        )
        if any(
            item.status in {RefundStatus.PENDING, RefundStatus.PROCESSING}
            for item in previous
        ):
            raise HTTPException(
                status_code=409, detail="Another refund is still being processed."
            )
        refundable = payment.amount_minor - sum(
            item.amount_minor
            for item in previous
            if item.status == RefundStatus.PROCESSED
        )
        if amount_minor <= 0 or amount_minor > refundable:
            raise HTTPException(
                status_code=422,
                detail=f"Refund must be between 1 and {refundable} minor units.",
            )
        tutor_share = (
            amount_minor * payment.tutor_earning_minor + payment.amount_minor // 2
        ) // payment.amount_minor
        refund = PaymentRefund(
            payment_id=payment.id,
            requested_by_user_id=admin.id,
            provider=payment.provider,
            provider_reference=f"tutova-refund-{uuid.uuid4().hex}",
            amount_minor=amount_minor,
            tutor_share_minor=tutor_share,
            platform_share_minor=amount_minor - tutor_share,
            currency=payment.currency,
            status=RefundStatus.PENDING,
            reason=reason[:500],
        )
        self.db.add(refund)
        await self.db.commit()
        await self.db.refresh(refund)
        try:
            result = await self._get_provider().initiate_refund(
                transaction_reference=payment.provider_reference,
                reference=refund.provider_reference,
                amount_minor=amount_minor,
                currency=payment.currency,
                reason=reason,
            )
        except (PaystackError, ValueError) as exc:
            # Avoid opening a second refund when the provider may have accepted
            # the first request but its response was lost.
            refund.status = RefundStatus.PROCESSING
            refund.failure_reason = "Provider response uncertain; verify this refund reference before retrying."
            await self.db.commit()
            raise HTTPException(
                status_code=502,
                detail="Refund submission is unconfirmed. Verify the refund reference before retrying.",
            ) from exc
        if result["status"] in {"PROCESSED", "SUCCESS", "SUCCESSFUL"}:
            refund.status = RefundStatus.PROCESSED
            refund.processed_at = datetime.now(timezone.utc)
            payment.status = (
                PaymentStatus.REFUNDED
                if amount_minor == refundable
                else PaymentStatus.PARTIALLY_REFUNDED
            )
        else:
            refund.status = RefundStatus.PROCESSING
        await self.db.commit()
        await self.db.refresh(refund)
        return refund

    async def verify_refund(self, refund_id: uuid.UUID):
        from app.domain.payments.models.payout import PaymentRefund, RefundStatus

        refund = await self.db.scalar(
            select(PaymentRefund).where(PaymentRefund.id == refund_id).with_for_update()
        )
        if refund is None:
            raise HTTPException(status_code=404, detail="Refund not found.")
        try:
            result = await self._get_provider().verify_refund(
                provider_reference=refund.provider_reference
            )
        except PaystackError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if result["amount_minor"] != refund.amount_minor:
            raise HTTPException(
                status_code=409,
                detail="Verified refund amount does not match the recorded refund.",
            )
        status_value = str(result["status"]).upper()
        if status_value in {"PROCESSED", "SUCCESS", "SUCCESSFUL"}:
            refund.status = RefundStatus.PROCESSED
            refund.processed_at = refund.processed_at or datetime.now(timezone.utc)
            payment = await self.db.get(Payment, refund.payment_id)
            prior = await self.db.scalar(
                select(func.coalesce(func.sum(PaymentRefund.amount_minor), 0)).where(
                    PaymentRefund.payment_id == payment.id,
                    PaymentRefund.status == RefundStatus.PROCESSED,
                )
            )
            payment.status = (
                PaymentStatus.REFUNDED
                if prior >= payment.amount_minor
                else PaymentStatus.PARTIALLY_REFUNDED
            )
        elif status_value in {"FAILED", "CANCELLED"}:
            refund.status = RefundStatus.FAILED
            refund.failure_reason = f"Paystack refund status: {status_value}"
        else:
            refund.status = RefundStatus.PROCESSING
        await self.db.commit()
        await self.db.refresh(refund)
        return refund

    async def list_all_payouts(self):
        from app.domain.payments.models.payout import TutorPayout

        return list(
            (
                await self.db.scalars(
                    select(TutorPayout).order_by(TutorPayout.created_at.desc())
                )
            ).all()
        )

    async def list_all_refunds(self):
        from app.domain.payments.models.payout import PaymentRefund

        return list(
            (
                await self.db.scalars(
                    select(PaymentRefund).order_by(PaymentRefund.created_at.desc())
                )
            ).all()
        )
