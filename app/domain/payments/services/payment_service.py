import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.authentication.models.user import User
from app.domain.payments.models.payment import Payment, PaymentStatus
from app.domain.payments.paystack import PaystackError, PaystackProvider
from app.domain.payments.services.commission_policy import (
    build_monthly_commission_schedule,
    commission_bps_for_tenure,
    completed_tenure_months,
    split_monthly_commission,
)
from app.domain.session_bookings.models.lesson_booking import (
    BookingStatus,
    LessonBooking,
)
from app.domain.session_bookings.models.monthly_arrangement import (
    MonthlyArrangementStatus,
    MonthlyTutoringArrangement,
)
from app.domain.session_bookings.schemas.booking import BookingCreate
from app.domain.session_bookings.services.booking_service import BookingService
from app.domain.tutoring_requests.models.tutoring_request import (
    TutoringRequest,
    TutoringRequestStatus,
)
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)


TUTOVA_TIMEZONE = timezone(timedelta(hours=1))  # Nigeria West Africa Time (UTC+1)


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
    def _commission_bps(completed_months: Decimal) -> int:
        """Compatibility wrapper for the tenure-based commission tiers."""
        return commission_bps_for_tenure(completed_months)

    async def _tutor_tenure_months(
        self, tutor_profile: TutorProfile, as_of: date | datetime | None = None
    ) -> int:
        verification = await self.db.scalar(
            select(TutorVerification).where(
                TutorVerification.tutor_user_id == tutor_profile.user_id
            )
        )
        if verification is None or verification.status != VerificationStatus.APPROVED:
            raise HTTPException(
                status_code=409,
                detail="The tutor must have an active administrator approval before payment can be initialized.",
            )
        if verification.approved_at is None:
            raise HTTPException(
                status_code=409,
                detail="The tutor approval date is missing. Please contact Tutova support.",
            )
        return completed_tenure_months(
            verification.approved_at,
            as_of or datetime.now(TUTOVA_TIMEZONE),
        )

    @staticmethod
    def _scheduled_month_amount(
        arrangement: MonthlyTutoringArrangement, period_start: date
    ) -> int | None:
        for item in arrangement.commission_schedule or []:
            if item.get("period_start") == period_start.isoformat():
                return int(item["tutor_earning_minor"])
        return None

    async def initialize_request_payment(
        self, user: User, request_id: uuid.UUID, payload: BookingCreate, idempotency_key: str
    ) -> Payment:
        """Collect payment against a proposed lesson before creating its booking."""
        if not idempotency_key or len(idempotency_key) > 120:
            raise HTTPException(status_code=422, detail="A valid Idempotency-Key is required.")

        existing = await self.db.scalar(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        if existing is not None:
            if existing.requester_user_id != user.id or existing.tutoring_request_id != request_id:
                raise HTTPException(status_code=409, detail="Idempotency key already used.")
            if existing.status == PaymentStatus.FAILED:
                raise HTTPException(status_code=409, detail="This payment attempt failed. Start a new payment attempt.")
            if existing.status == PaymentStatus.PAID:
                raise HTTPException(status_code=409, detail="This tutoring request has already been paid.")
            if existing.checkout_url:
                return existing
            provider = self._get_provider()
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

        role = str(getattr(user.role, "value", user.role)).upper()
        if role not in {"PARENT", "ADULT_LEARNER"}:
            raise HTTPException(status_code=403, detail="Only parents and adult learners can pay for lessons.")

        request = await self.db.scalar(
            select(TutoringRequest).where(TutoringRequest.id == request_id).with_for_update()
        )
        if request is None:
            raise HTTPException(status_code=404, detail="Tutoring request not found.")
        if request.requester_user_id != user.id:
            raise HTTPException(status_code=403, detail="You cannot pay for this tutoring request.")
        if request.status != TutoringRequestStatus.ACCEPTED or request.assigned_tutor_id is None:
            raise HTTPException(status_code=409, detail="The tutoring request must have an assigned tutor before payment.")

        start_at = payload.start_at.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if start_at <= now:
            raise HTTPException(status_code=422, detail="The lesson time must be in the future.")
        period_start = payload.start_at.date()
        end_at = start_at + timedelta(minutes=payload.duration_minutes)

        tutor = await self.db.scalar(
            select(TutorProfile).where(TutorProfile.id == request.assigned_tutor_id).with_for_update()
        )
        if tutor is None or tutor.monthly_fee is None or Decimal(str(tutor.monthly_fee)) <= 0:
            raise HTTPException(status_code=409, detail="The assigned tutor has not set a valid monthly tutoring fee.")
        verification = await self.db.scalar(
            select(TutorVerification).where(TutorVerification.tutor_user_id == tutor.user_id)
        )
        if verification is None or verification.status != VerificationStatus.APPROVED or verification.approved_at is None:
            raise HTTPException(status_code=409, detail="The tutor must have administrator approval before payment.")

        monthly_fee_minor = int((Decimal(str(tutor.monthly_fee)) * Decimal(100)).quantize(Decimal("1")))
        duration_months = payload.contract_months
        month_index = period_start.month - 1 + duration_months
        period_end = date(period_start.year + month_index // 12, month_index % 12 + 1, 1) - timedelta(days=1)

        arrangement = await self.db.scalar(
            select(MonthlyTutoringArrangement).where(
                MonthlyTutoringArrangement.tutoring_request_id == request.id,
                MonthlyTutoringArrangement.period_start == period_start,
            ).with_for_update()
        )
        if arrangement is None:
            schedule = build_monthly_commission_schedule(
                monthly_fee_minor=monthly_fee_minor,
                duration_months=duration_months,
                period_start=period_start,
                tutor_approved_at=verification.approved_at,
            )
            arrangement = MonthlyTutoringArrangement(
                tutoring_request_id=request.id,
                tutor_profile_id=tutor.id,
                requester_user_id=user.id,
                monthly_fee_minor=monthly_fee_minor,
                duration_months=duration_months,
                commission_bps=int(schedule[0]["commission_bps"]),
                platform_fee_minor=sum(int(x["platform_fee_minor"]) for x in schedule),
                tutor_commission_minor=sum(int(x["tutor_commission_minor"]) for x in schedule),
                learner_fee_minor=sum(int(x["learner_fee_minor"]) for x in schedule),
                tutor_earning_minor=sum(int(x["tutor_earning_minor"]) for x in schedule),
                commission_schedule=schedule,
                completed_months_at_creation=Decimal(await self._tutor_tenure_months(tutor, period_start)),
                currency="NGN",
                period_start=period_start,
                period_end=period_end,
                status=MonthlyArrangementStatus.PENDING_PAYMENT,
            )
            self.db.add(arrangement)
            await self.db.flush()
        else:
            if arrangement.tutor_profile_id != tutor.id or arrangement.monthly_fee_minor != monthly_fee_minor or arrangement.duration_months != duration_months:
                raise HTTPException(status_code=409, detail="A different tutoring arrangement already exists for this request and start date.")
            if arrangement.status == MonthlyArrangementStatus.ACTIVE:
                raise HTTPException(
                    status_code=409,
                    detail="This tutoring contract has already been paid. Create additional lessons using its existing arrangement instead of paying again.",
                )
            if arrangement.status in {MonthlyArrangementStatus.CANCELLED, MonthlyArrangementStatus.EXPIRED}:
                arrangement.status = MonthlyArrangementStatus.PENDING_PAYMENT

        # Do not permit payment checkout for a time that is already occupied.
        from app.domain.session_bookings.repositories.booking_repository import BookingRepository
        booking_repo = BookingRepository(self.db)
        if await booking_repo.has_tutor_conflict(tutor.id, start_at, end_at) or await booking_repo.has_requester_conflict(user.id, start_at, end_at):
            raise HTTPException(status_code=409, detail="The selected lesson time is no longer available.")

        # Reuse an unresolved checkout for this arrangement rather than
        # creating concurrent Paystack attempts that could both be paid.
        pending_attempt = await self.db.scalar(
            select(Payment).where(
                Payment.monthly_arrangement_id == arrangement.id,
                Payment.status == PaymentStatus.PENDING,
            ).order_by(Payment.created_at.desc())
        )
        if pending_attempt is not None:
            if (
                pending_attempt.proposed_start_at != start_at
                or pending_attempt.proposed_duration_minutes != payload.duration_minutes
            ):
                raise HTTPException(
                    status_code=409,
                    detail="A payment checkout is already pending for this contract with different lesson details. Complete it or wait for its status to be reconciled before changing the schedule.",
                )
            if pending_attempt.checkout_url:
                return pending_attempt
            provider = self._get_provider()
            pending_attempt.checkout_url = await provider.initialize_payment(
                reference=pending_attempt.provider_reference,
                amount_minor=pending_attempt.amount_minor,
                currency=pending_attempt.currency,
                email=user.email,
            )
            await self.db.commit()
            await self.db.refresh(pending_attempt)
            return pending_attempt

        tutoring_amount = arrangement.monthly_fee_minor * arrangement.duration_months
        learner_fee = arrangement.learner_fee_minor
        amount_minor = tutoring_amount + learner_fee
        provider = self._get_provider()
        payment = Payment(
            booking_id=None,
            tutoring_request_id=request.id,
            proposed_start_at=start_at,
            proposed_duration_minutes=payload.duration_minutes,
            proposed_lesson_notes=payload.lesson_notes,
            proposed_contract_months=duration_months,
            monthly_arrangement_id=arrangement.id,
            requester_user_id=user.id,
            tutor_profile_id=tutor.id,
            provider=provider.name,
            provider_reference=f"tutova-{uuid.uuid4().hex}",
            idempotency_key=idempotency_key,
            amount_minor=amount_minor,
            tutoring_amount_minor=tutoring_amount,
            tutor_commission_minor=arrangement.tutor_commission_minor,
            learner_fee_minor=learner_fee,
            currency=arrangement.currency,
            commission_bps=arrangement.commission_bps,
            platform_fee_minor=arrangement.platform_fee_minor,
            tutor_earning_minor=arrangement.tutor_earning_minor,
            tutor_completed_hours_at_payment=Decimal("0"),
            tutor_completed_months_at_payment=arrangement.completed_months_at_creation,
            status=PaymentStatus.PENDING,
        )
        self.db.add(payment)
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
        arrangement = None
        if booking.monthly_arrangement_id is not None:
            arrangement = await self.db.scalar(
                select(MonthlyTutoringArrangement)
                .where(MonthlyTutoringArrangement.id == booking.monthly_arrangement_id)
                .with_for_update()
            )
            if arrangement is None:
                raise HTTPException(status_code=409, detail="The tutoring arrangement could not be found.")
            if arrangement.requester_user_id != user.id:
                raise HTTPException(status_code=403, detail="You cannot pay for this arrangement.")
            gross = arrangement.monthly_fee_minor * arrangement.duration_months
        else:
            gross = booking.gross_amount_minor or 0
        if gross <= 0:
            raise HTTPException(
                status_code=409, detail="This booking has no valid monthly contract price."
            )

        pending_query = select(Payment).where(
            Payment.status == PaymentStatus.PENDING,
        )
        if arrangement is not None:
            pending_query = pending_query.where(Payment.monthly_arrangement_id == arrangement.id)
        else:
            pending_query = pending_query.where(Payment.booking_id == booking.id)
        pending_payment = await self.db.scalar(
            pending_query.order_by(Payment.created_at.desc())
        )
        if pending_payment is not None:
            raise HTTPException(
                status_code=409,
                detail=f"A payment is already awaiting completion. Retrieve payment {pending_payment.id} to reuse its checkout URL.",
            )

        paid_query = select(Payment.id).where(Payment.status == PaymentStatus.PAID)
        if arrangement is not None:
            paid_query = paid_query.where(Payment.monthly_arrangement_id == arrangement.id)
        else:
            paid_query = paid_query.where(Payment.booking_id == booking.id)
        already_paid = await self.db.scalar(paid_query)
        if already_paid:
            raise HTTPException(
                status_code=409, detail="This booking has already been paid."
            )

        tutor = await self.db.get(TutorProfile, booking.tutor_profile_id)
        if tutor is None:
            raise HTTPException(status_code=404, detail="Tutor profile not found.")

        completed_months = Decimal(await self._tutor_tenure_months(tutor))
        if arrangement is not None:
            commission_bps = arrangement.commission_bps
            tutoring_amount = gross
            platform_fee = arrangement.platform_fee_minor
            tutor_commission = arrangement.tutor_commission_minor
            learner_fee = arrangement.learner_fee_minor
            tutor_earning = arrangement.tutor_earning_minor
            # Existing arrangements created before the split-policy migration
            # have zero split fields. Preserve their original charge and earnings.
            if not arrangement.commission_schedule:
                tutoring_amount = gross
                tutor_commission = 0
                learner_fee = 0
                platform_fee = arrangement.platform_fee_minor
                tutor_earning = arrangement.tutor_earning_minor
            learner_total = tutoring_amount + learner_fee
        else:
            commission_bps = self._commission_bps(completed_months)
            split = split_monthly_commission(gross, commission_bps)
            tutoring_amount = gross
            platform_fee = split["platform_fee_minor"]
            tutor_commission = split["tutor_commission_minor"]
            learner_fee = split["learner_fee_minor"]
            tutor_earning = split["tutor_earning_minor"]
            learner_total = split["learner_total_minor"]

        payment = Payment(
            booking_id=booking.id,
            monthly_arrangement_id=arrangement.id if arrangement else None,
            requester_user_id=user.id,
            tutor_profile_id=tutor.id,
            provider=provider.name,
            provider_reference=f"tutova-{uuid.uuid4().hex}",
            idempotency_key=idempotency_key,
            amount_minor=learner_total,
            tutoring_amount_minor=tutoring_amount,
            tutor_commission_minor=tutor_commission,
            learner_fee_minor=learner_fee,
            currency=booking.currency or "NGN",
            commission_bps=commission_bps,
            platform_fee_minor=platform_fee,
            tutor_earning_minor=tutor_earning,
            tutor_completed_hours_at_payment=Decimal("0"),
            tutor_completed_months_at_payment=completed_months.quantize(Decimal("0.01")),
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
        # A request-based payment has no booking yet. Create it only after the
        # provider has confirmed the exact amount/reference/currency above.
        if payment.tutoring_request_id is not None and payment.booking_id is None:
            if payment.proposed_start_at is None or payment.proposed_duration_minutes is None or payment.monthly_arrangement_id is None:
                raise HTTPException(status_code=409, detail="The paid booking details are incomplete. Contact Tutova support.")
            requester = await self.db.get(User, payment.requester_user_id)
            if requester is None:
                raise HTTPException(status_code=409, detail="The payment requester account no longer exists.")
            existing_booking = await self.db.scalar(
                select(LessonBooking).where(
                    LessonBooking.monthly_arrangement_id == payment.monthly_arrangement_id
                )
            )
            if existing_booking is not None:
                payment.booking_id = existing_booking.id
            else:
                booking = await BookingService(self.db).create_booking(
                    requester,
                    payment.tutoring_request_id,
                    BookingCreate(
                        start_at=payment.proposed_start_at,
                        duration_minutes=payment.proposed_duration_minutes,
                        contract_months=payment.proposed_contract_months or 1,
                        monthly_arrangement_id=payment.monthly_arrangement_id,
                        lesson_notes=payment.proposed_lesson_notes,
                    ),
                    payment_verified=True,
                )
                payment.booking_id = booking.id

        payment.status = PaymentStatus.PAID
        payment.paid_at = datetime.now(timezone.utc)
        payment.failure_reason = None
        if payment.monthly_arrangement_id is not None:
            arrangement = await self.db.get(MonthlyTutoringArrangement, payment.monthly_arrangement_id)
            if arrangement is not None:
                arrangement.status = MonthlyArrangementStatus.ACTIVE
                arrangement.paid_at = payment.paid_at
                arrangement.activated_at = payment.paid_at
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
        if event.event_type in {"charge.success", "charge.failed"}:
            # Verification against Paystack's API is authoritative for both
            # successful and failed charge events.
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

    @staticmethod
    def _contract_month_window(arrangement: MonthlyTutoringArrangement, offset: int):
        # Match the calendar-month contract boundaries established when the
        # arrangement is created: the first period may be a partial month.
        month_index = arrangement.period_start.month - 1 + offset
        year = arrangement.period_start.year + month_index // 12
        month = month_index % 12 + 1
        month_start = date(year, month, 1)
        next_month_index = month_index + 1
        next_year = arrangement.period_start.year + next_month_index // 12
        next_month = next_month_index % 12 + 1
        month_end = date(next_year, next_month, 1) - timedelta(days=1)
        return (
            max(arrangement.period_start, month_start),
            min(arrangement.period_end, month_end),
        )

    async def request_payout(
        self,
        user: User,
        payment_id: uuid.UUID,
        *,
        earning_period_start: date | None = None,
    ):
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
            raise HTTPException(status_code=409, detail="Only successfully paid contracts can be paid out.")

        arrangement = None
        payout_period_start = None
        payout_period_end = None
        if payment.monthly_arrangement_id is not None:
            arrangement = await self.db.get(
                MonthlyTutoringArrangement, payment.monthly_arrangement_id
            )
            if arrangement is None or earning_period_start is None:
                raise HTTPException(
                    status_code=422,
                    detail="Select the completed contract month for this payout.",
                )
            valid_period = None
            for offset in range(arrangement.duration_months):
                window = self._contract_month_window(arrangement, offset)
                if window[0] == earning_period_start:
                    valid_period = window
                    break
            if valid_period is None:
                raise HTTPException(status_code=422, detail="The selected payout month is not part of this contract.")
            payout_period_start, payout_period_end = valid_period
            if payout_period_end > datetime.now(TUTOVA_TIMEZONE).date():
                raise HTTPException(status_code=409, detail="This month's tutor earnings are still being held until month-end.")

            month_start_dt = datetime.combine(payout_period_start, datetime.min.time(), tzinfo=TUTOVA_TIMEZONE)
            month_end_dt = datetime.combine(payout_period_end + timedelta(days=1), datetime.min.time(), tzinfo=TUTOVA_TIMEZONE)
            lessons = list((await self.db.scalars(
                select(LessonBooking).where(
                    LessonBooking.monthly_arrangement_id == arrangement.id,
                    LessonBooking.start_at >= month_start_dt,
                    LessonBooking.start_at < month_end_dt,
                    LessonBooking.status.notin_([BookingStatus.CANCELLED, BookingStatus.DECLINED]),
                )
            )).all())
            if not lessons or any(
                lesson.status != BookingStatus.COMPLETED
                or lesson.learner_acknowledged_at is None
                or lesson.disputed_at is not None
                or (lesson.admin_review_required_at is not None and lesson.admin_reviewed_at is None)
                for lesson in lessons
            ):
                raise HTTPException(
                    status_code=409,
                    detail="All lessons scheduled for this contract month must be completed, acknowledged and clear of unresolved review before payout.",
                )
            payable = self._scheduled_month_amount(arrangement, payout_period_start)
            if payable is None:
                # Legacy arrangements predate per-month commission snapshots.
                base_share, remainder = divmod(
                    payment.tutor_earning_minor, arrangement.duration_months
                )
                month_offset = (
                    (payout_period_start.year - arrangement.period_start.year) * 12
                    + payout_period_start.month - arrangement.period_start.month
                )
                payable = base_share + (
                    remainder if month_offset == arrangement.duration_months - 1 else 0
                )
        else:
            booking = await self.db.get(LessonBooking, payment.booking_id) if payment.booking_id else None
            if (
                booking is None
                or booking.status != BookingStatus.COMPLETED
                or booking.learner_acknowledged_at is None
                or booking.disputed_at is not None
                or booking.admin_review_required_at is not None
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Tutor earnings become payable after lesson completion and learner acknowledgement.",
                )
            payable = payment.tutor_earning_minor

        recipient = await self.db.scalar(
            select(PayoutRecipient).where(
                PayoutRecipient.tutor_profile_id == tutor.id,
                PayoutRecipient.is_active.is_(True),
            )
        )
        if recipient is None:
            raise HTTPException(status_code=409, detail="Add and verify a bank account before requesting payout.")

        existing_query = select(TutorPayout).where(TutorPayout.payment_id == payment.id)
        if payout_period_start is None:
            existing_query = existing_query.where(TutorPayout.earning_period_start.is_(None))
        else:
            existing_query = existing_query.where(TutorPayout.earning_period_start == payout_period_start)
        existing = await self.db.scalar(existing_query)
        if existing:
            raise HTTPException(status_code=409, detail="A payout has already been requested for this earning period.")

        refunds = list((await self.db.scalars(
            select(PaymentRefund).where(
                PaymentRefund.payment_id == payment.id,
                PaymentRefund.status != RefundStatus.FAILED,
            )
        )).all())
        if any(refund.status in {RefundStatus.PENDING, RefundStatus.PROCESSING} for refund in refunds):
            raise HTTPException(status_code=409, detail="A refund is being processed for this contract.")
        refunded_tutor_share = sum(
            refund.tutor_share_minor
            for refund in refunds
            if refund.status == RefundStatus.PROCESSED
        )
        if arrangement is not None and payment.tutor_earning_minor > 0:
            refunded_tutor_share = (
                refunded_tutor_share * payable // payment.tutor_earning_minor
            )
        payable -= refunded_tutor_share
        if payable <= 0:
            raise HTTPException(status_code=409, detail="There are no tutor earnings available for this period.")

        payout = TutorPayout(
            tutor_profile_id=tutor.id,
            payment_id=payment.id,
            earning_period_start=payout_period_start,
            earning_period_end=payout_period_end,
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

        payments = list((await self.db.scalars(
            select(Payment).where(
                Payment.tutor_profile_id == tutor_id,
                Payment.status.in_([PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED]),
            ).order_by(Payment.paid_at.asc())
        )).all())
        eligible = []
        for payment in payments:
            refunds = list((await self.db.scalars(
                select(PaymentRefund).where(
                    PaymentRefund.payment_id == payment.id,
                    PaymentRefund.status != RefundStatus.FAILED,
                )
            )).all())
            if any(refund.status in {RefundStatus.PENDING, RefundStatus.PROCESSING} for refund in refunds):
                continue
            refunded_tutor_share = sum(
                item.tutor_share_minor for item in refunds
                if item.status == RefundStatus.PROCESSED
            )

            if payment.monthly_arrangement_id is not None:
                arrangement = await self.db.get(
                    MonthlyTutoringArrangement, payment.monthly_arrangement_id
                )
                if arrangement is None:
                    continue
                for offset in range(arrangement.duration_months):
                    period_start, period_end = self._contract_month_window(arrangement, offset)
                    if period_end > datetime.now(TUTOVA_TIMEZONE).date():
                        continue
                    month_start_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=TUTOVA_TIMEZONE)
                    month_end_dt = datetime.combine(period_end + timedelta(days=1), datetime.min.time(), tzinfo=TUTOVA_TIMEZONE)
                    lessons = list((await self.db.scalars(
                        select(LessonBooking).where(
                            LessonBooking.monthly_arrangement_id == arrangement.id,
                            LessonBooking.start_at >= month_start_dt,
                            LessonBooking.start_at < month_end_dt,
                            LessonBooking.status.notin_([BookingStatus.CANCELLED, BookingStatus.DECLINED]),
                        )
                    )).all())
                    if not lessons or any(
                        lesson.status != BookingStatus.COMPLETED
                        or lesson.learner_acknowledged_at is None
                        or lesson.disputed_at is not None
                        or (lesson.admin_review_required_at is not None and lesson.admin_reviewed_at is None)
                        for lesson in lessons
                    ):
                        continue
                    existing = await self.db.scalar(
                        select(TutorPayout.id).where(
                            TutorPayout.payment_id == payment.id,
                            TutorPayout.earning_period_start == period_start,
                        )
                    )
                    if existing:
                        continue
                    installment = self._scheduled_month_amount(arrangement, period_start)
                    if installment is None:
                        # Legacy arrangements predate per-month commission snapshots.
                        base_share, remainder = divmod(
                            payment.tutor_earning_minor, arrangement.duration_months
                        )
                        month_offset = (
                            (period_start.year - arrangement.period_start.year) * 12
                            + period_start.month - arrangement.period_start.month
                        )
                        installment = base_share + (
                            remainder if month_offset == arrangement.duration_months - 1 else 0
                        )
                    refund_share = (
                        refunded_tutor_share * installment // payment.tutor_earning_minor
                        if payment.tutor_earning_minor > 0 else 0
                    )
                    available = installment - refund_share
                    if available > 0:
                        eligible.append({
                            "payment_id": payment.id,
                            "booking_id": payment.booking_id,
                            "earning_period_start": period_start,
                            "earning_period_end": period_end,
                            "gross_amount_minor": payment.tutoring_amount_minor,
                            "available_amount_minor": available,
                            "currency": payment.currency,
                            "paid_at": payment.paid_at,
                        })
                continue

            booking = await self.db.get(LessonBooking, payment.booking_id) if payment.booking_id else None
            if (
                booking is None
                or booking.status != BookingStatus.COMPLETED
                or booking.learner_acknowledged_at is None
                or booking.disputed_at is not None
                or booking.admin_review_required_at is not None
            ):
                continue
            existing = await self.db.scalar(
                select(TutorPayout.id).where(
                    TutorPayout.payment_id == payment.id,
                    TutorPayout.earning_period_start.is_(None),
                )
            )
            if existing:
                continue
            available = payment.tutor_earning_minor - refunded_tutor_share
            if available > 0:
                eligible.append({
                    "payment_id": payment.id,
                    "booking_id": payment.booking_id,
                    "earning_period_start": None,
                    "earning_period_end": None,
                    "gross_amount_minor": payment.tutoring_amount_minor,
                    "available_amount_minor": available,
                    "currency": payment.currency,
                    "paid_at": payment.paid_at,
                })
        return eligible

    async def get_earnings_summary(self, user: User) -> dict:
        """Summarize paid contract earnings and the current month's accrued share."""
        from app.domain.payments.models.payout import PayoutStatus, TutorPayout

        tutor_id = await self.db.scalar(
            select(TutorProfile.id).where(TutorProfile.user_id == user.id)
        )
        if tutor_id is None:
            raise HTTPException(status_code=404, detail="Tutor profile not found.")

        payments = list((await self.db.scalars(
            select(Payment).where(
                Payment.tutor_profile_id == tutor_id,
                Payment.status.in_([PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED]),
            )
        )).all())
        payouts = list((await self.db.scalars(
            select(TutorPayout).where(TutorPayout.tutor_profile_id == tutor_id)
        )).all())

        total_gross = sum(payment.amount_minor for payment in payments)
        total_commission = sum(payment.platform_fee_minor for payment in payments)
        total_tutor_commission = sum(payment.tutor_commission_minor for payment in payments)
        total_learner_fees = sum(payment.learner_fee_minor for payment in payments)
        total_tutor_earnings = sum(payment.tutor_earning_minor for payment in payments)
        paid_out = sum(
            payout.amount_minor for payout in payouts if payout.status == PayoutStatus.PAID
        )
        today = datetime.now(TUTOVA_TIMEZONE).date()
        current_month_earnings = 0
        for payment in payments:
            if payment.monthly_arrangement_id is None:
                continue
            arrangement = await self.db.get(
                MonthlyTutoringArrangement, payment.monthly_arrangement_id
            )
            if arrangement is None:
                continue
            for offset in range(arrangement.duration_months):
                period_start, period_end = self._contract_month_window(arrangement, offset)
                if period_start <= today <= period_end:
                    amount = self._scheduled_month_amount(arrangement, period_start)
                    if amount is None:
                        base_share, remainder = divmod(
                            payment.tutor_earning_minor, arrangement.duration_months
                        )
                        amount = base_share + (
                            remainder if offset == arrangement.duration_months - 1 else 0
                        )
                    current_month_earnings += amount
                    break

        return {
            "currency": "NGN",
            "total_contract_amount_minor": total_gross,
            "total_platform_commission_minor": total_commission,
            "total_tutor_commission_minor": total_tutor_commission,
            "total_learner_fee_minor": total_learner_fees,
            "total_tutor_earnings_minor": total_tutor_earnings,
            "current_month_earnings_minor": current_month_earnings,
            "paid_out_minor": paid_out,
            "held_tutor_earnings_minor": max(total_tutor_earnings - paid_out, 0),
        }

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
