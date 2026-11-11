import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.models.user import User
from app.domain.notifications.models.notification import NotificationType
from app.domain.notifications.services.notification_service import NotificationService
from app.domain.payments.models.payment import Payment, PaymentStatus
from app.domain.session_bookings.models.lesson_booking import (
    BookingStatus,
    LessonBooking,
)
from app.domain.session_bookings.repositories.booking_repository import (
    BookingRepository,
)
from app.domain.session_bookings.schemas.booking import (
    BookingAccept,
    BookingCreate,
    BookingResponse,
)
from app.domain.tutoring_requests.models.tutoring_request import (
    TutoringMode,
    TutoringRequest,
    TutoringRequestStatus,
)
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)


class BookingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.bookings = BookingRepository(db)

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    async def _get_verified_tutor(
        self,
        user: User,
    ) -> TutorProfile:
        if str(getattr(user.role, "value", user.role)).upper() != "TUTOR":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tutors can perform this action.",
            )

        result = await self.db.execute(
            select(TutorProfile).where(TutorProfile.user_id == user.id)
        )
        tutor = result.scalar_one_or_none()

        if tutor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tutor profile not found.",
            )

        verification_result = await self.db.execute(
            select(TutorVerification).where(TutorVerification.tutor_user_id == user.id)
        )
        verification = verification_result.scalar_one_or_none()

        if verification is None or verification.status != VerificationStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your tutor verification must be approved.",
            )

        return tutor

    async def _get_requester(self, user: User) -> User:
        role = str(getattr(user.role, "value", user.role)).upper()

        allowed_roles = {
            "PARENT",
            "ADULT_LEARNER",
        }

        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=("Only parents and adult learners can request lesson bookings."),
            )

        return user

    async def _get_request_for_update(
        self,
        request_id: uuid.UUID,
    ) -> TutoringRequest:
        result = await self.db.execute(
            select(TutoringRequest)
            .where(TutoringRequest.id == request_id)
            .with_for_update()
        )
        request = result.scalar_one_or_none()

        if request is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tutoring request not found.",
            )

        return request

    async def _get_booking_tutor_user_id(
        self,
        booking: LessonBooking,
    ) -> uuid.UUID | None:
        result = await self.db.execute(
            select(TutorProfile.user_id).where(
                TutorProfile.id == booking.tutor_profile_id
            )
        )
        return result.scalar_one_or_none()

    # ---------------------------------------------------------
    # Create booking - Parent / Adult learner
    # ---------------------------------------------------------

    async def create_booking(
        self,
        user: User,
        request_id: uuid.UUID,
        payload: BookingCreate,
    ) -> BookingResponse:
        await self._get_requester(user)

        # Lock the accepted tutoring request first.
        request = await self._get_request_for_update(request_id)

        if request.requester_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot schedule a lesson for this request.",
            )

        if request.status != TutoringRequestStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A lesson can only be scheduled for an accepted tutoring request."
                ),
            )

        if request.assigned_tutor_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This tutoring request has no assigned tutor.",
            )

        start_at = payload.start_at.astimezone(timezone.utc)

        if start_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The lesson time must be in the future.",
            )

        end_at = start_at + timedelta(minutes=payload.duration_minutes)

        # Lock order: tutoring request -> requester -> tutor.
        # This serializes overlapping booking creation for the learner
        # and the assigned tutor.
        locked_requester = await self.bookings.lock_requester(user.id)

        if locked_requester is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner account not found.",
            )

        locked_tutor = await self.bookings.lock_tutor(request.assigned_tutor_id)

        if locked_tutor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tutor profile not found.",
            )

        if (
            locked_tutor.hourly_rate is None
            or Decimal(str(locked_tutor.hourly_rate)) <= 0
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("The assigned tutor does not have a valid hourly rate."),
            )

        hourly_rate = Decimal(str(locked_tutor.hourly_rate))

        gross_amount_minor = int(
            (
                hourly_rate
                * Decimal(100)
                * Decimal(payload.duration_minutes)
                / Decimal(60)
            ).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )

        if await self.bookings.has_tutor_conflict(
            tutor_profile_id=locked_tutor.id,
            start_at=start_at,
            end_at=end_at,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("The tutor already has another booking during this time."),
            )

        if await self.bookings.has_requester_conflict(
            requester_user_id=user.id,
            start_at=start_at,
            end_at=end_at,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("You already have another booking during this time."),
            )

        # The learner does not supply a meeting link.
        # The tutor may supply one when accepting the booking.
        if request.tutoring_mode == TutoringMode.IN_PERSON:
            if request.location_id is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=("The accepted request has no agreed in-person location."),
                )

            location_id = request.location_id
        else:
            location_id = None

        booking = LessonBooking(
            tutoring_request_id=request.id,
            tutor_profile_id=locked_tutor.id,
            requester_user_id=user.id,
            start_at=start_at,
            end_at=end_at,
            duration_minutes=payload.duration_minutes,
            hourly_rate=hourly_rate,
            gross_amount_minor=gross_amount_minor,
            currency="NGN",
            status=BookingStatus.PENDING_TUTOR_CONFIRMATION,
            meeting_link=None,
            location_id=location_id,
            lesson_notes=payload.lesson_notes,
        )

        try:
            await self.bookings.create(booking)
            await self.bookings.commit()
            await self.db.refresh(booking)

            return BookingResponse.model_validate(booking)

        except Exception:
            await self.bookings.rollback()
            raise

    # ---------------------------------------------------------
    # List bookings
    # ---------------------------------------------------------

    async def list_my_bookings(
        self,
        user: User,
        limit: int = 20,
        offset: int = 0,
    ):
        bookings = await self.bookings.list_for_user(
            user_id=user.id,
            limit=limit,
            offset=offset,
        )

        return [BookingResponse.model_validate(booking) for booking in bookings]

    # ---------------------------------------------------------
    # Get booking
    # ---------------------------------------------------------

    async def get_booking(
        self,
        user: User,
        booking_id: uuid.UUID,
    ) -> BookingResponse:
        booking = await self.bookings.get_by_id(booking_id)

        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        tutor_user_id = await self._get_booking_tutor_user_id(booking)

        if booking.requester_user_id != user.id and tutor_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot access this booking.",
            )

        return BookingResponse.model_validate(booking)

    # ---------------------------------------------------------
    # Accept booking - Tutor
    # ---------------------------------------------------------

    async def accept_booking(
        self,
        user: User,
        booking_id: uuid.UUID,
        payload: BookingAccept,
    ) -> BookingResponse:
        tutor = await self._get_verified_tutor(user)

        booking = await self.bookings.get_by_id_for_update(booking_id)

        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        if booking.tutor_profile_id != tutor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this booking.",
            )

        if booking.status != BookingStatus.PENDING_TUTOR_CONFIRMATION:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This booking is not awaiting your acceptance.",
            )

        if booking.start_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("This requested lesson time has already passed."),
            )

        # Follow the same lock order used when creating bookings:
        # tutoring request -> requester -> tutor.
        request = await self._get_request_for_update(booking.tutoring_request_id)

        if request.status != TutoringRequestStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The tutoring request is no longer accepted. "
                    "This booking cannot be confirmed."
                ),
            )

        if request.assigned_tutor_id != tutor.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "You are no longer the tutor assigned to this tutoring request."
                ),
            )

        locked_requester = await self.bookings.lock_requester(booking.requester_user_id)

        if locked_requester is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner account not found.",
            )

        locked_tutor = await self.bookings.lock_tutor(tutor.id)

        if locked_tutor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tutor profile not found.",
            )

        if await self.bookings.has_tutor_conflict(
            tutor_profile_id=tutor.id,
            start_at=booking.start_at,
            end_at=booking.end_at,
            exclude_booking_id=booking.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("You are no longer available at the requested lesson time."),
            )

        if await self.bookings.has_requester_conflict(
            requester_user_id=booking.requester_user_id,
            start_at=booking.start_at,
            end_at=booking.end_at,
            exclude_booking_id=booking.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("The learner already has another booking during this time."),
            )

        if request.tutoring_mode == TutoringMode.IN_PERSON:
            if payload.meeting_link:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "A meeting link cannot be supplied for an in-person lesson."
                    ),
                )

            booking.meeting_link = None

        else:
            booking.meeting_link = payload.meeting_link

        try:
            booking.status = BookingStatus.CONFIRMED
            booking.confirmed_at = datetime.now(timezone.utc)

            await self.bookings.commit()
            await self.db.refresh(booking)

            return BookingResponse.model_validate(booking)

        except Exception:
            await self.bookings.rollback()
            raise

    # ---------------------------------------------------------
    # Legacy confirmation - Existing bookings only
    # ---------------------------------------------------------

    async def confirm_booking(
        self,
        user: User,
        booking_id: uuid.UUID,
    ) -> BookingResponse:
        """
        Retained for existing PENDING_CONFIRMATION bookings.

        New bookings use tutor acceptance instead.
        """
        booking = await self.bookings.get_by_id_for_update(booking_id)

        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        if booking.requester_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the requester can confirm this booking.",
            )

        if booking.status != BookingStatus.PENDING_CONFIRMATION:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("This booking is not awaiting legacy confirmation."),
            )

        if booking.start_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This proposed lesson time has already passed.",
            )

        try:
            locked_requester = await self.bookings.lock_requester(
                booking.requester_user_id
            )

            if locked_requester is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Learner account not found.",
                )

            locked_tutor = await self.bookings.lock_tutor(booking.tutor_profile_id)

            if locked_tutor is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tutor profile not found.",
                )

            if await self.bookings.has_tutor_conflict(
                tutor_profile_id=booking.tutor_profile_id,
                start_at=booking.start_at,
                end_at=booking.end_at,
                exclude_booking_id=booking.id,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=("The tutor is no longer available at this time."),
                )

            if await self.bookings.has_requester_conflict(
                requester_user_id=booking.requester_user_id,
                start_at=booking.start_at,
                end_at=booking.end_at,
                exclude_booking_id=booking.id,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=("You already have another booking during this time."),
                )

            booking.status = BookingStatus.CONFIRMED
            booking.confirmed_at = datetime.now(timezone.utc)

            await self.bookings.commit()
            await self.db.refresh(booking)

            return BookingResponse.model_validate(booking)

        except Exception:
            await self.bookings.rollback()
            raise

    # ---------------------------------------------------------
    # Decline booking
    # ---------------------------------------------------------

    async def decline_booking(
        self,
        user: User,
        booking_id: uuid.UUID,
        reason: str | None = None,
    ) -> BookingResponse:
        booking = await self.bookings.get_by_id_for_update(booking_id)

        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        # New workflow: the assigned tutor declines the booking.
        if booking.status == BookingStatus.PENDING_TUTOR_CONFIRMATION:
            tutor = await self._get_verified_tutor(user)

            if booking.tutor_profile_id != tutor.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not assigned to this booking.",
                )

        # Legacy workflow: requester can decline an old proposal.
        elif booking.status == BookingStatus.PENDING_CONFIRMATION:
            if booking.requester_user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Only the requester can decline this legacy booking proposal."
                    ),
                )

        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This booking cannot be declined.",
            )

        try:
            booking.status = BookingStatus.DECLINED
            booking.cancellation_reason = reason

            await self.bookings.commit()
            await self.db.refresh(booking)

            return BookingResponse.model_validate(booking)

        except Exception:
            await self.bookings.rollback()
            raise

    # ---------------------------------------------------------
    # Cancel booking - Either participant
    # ---------------------------------------------------------

    async def cancel_booking(
        self,
        user: User,
        booking_id: uuid.UUID,
        reason: str,
    ) -> BookingResponse:
        booking = await self.bookings.get_by_id_for_update(booking_id)

        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        tutor_user_id = await self._get_booking_tutor_user_id(booking)

        if booking.requester_user_id != user.id and tutor_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot cancel this booking.",
            )

        if booking.status not in {
            BookingStatus.PENDING_TUTOR_CONFIRMATION,
            BookingStatus.PENDING_CONFIRMATION,
            BookingStatus.CONFIRMED,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This booking cannot be cancelled.",
            )

        active_payment = await self.db.scalar(
            select(Payment.id)
            .where(
                Payment.booking_id == booking.id,
                Payment.status.in_(
                    [
                        PaymentStatus.PENDING,
                        PaymentStatus.PAID,
                    ]
                ),
            )
            .limit(1)
        )

        if active_payment is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This booking has an active or successful payment. "
                    "Payment resolution or an authorised refund is "
                    "required before cancellation."
                ),
            )

        try:
            booking.status = BookingStatus.CANCELLED
            booking.cancellation_reason = reason
            booking.cancelled_at = datetime.now(timezone.utc)

            await self.bookings.commit()
            await self.db.refresh(booking)

            return BookingResponse.model_validate(booking)

        except Exception:
            await self.bookings.rollback()
            raise

    # ---------------------------------------------------------
    # Complete booking - Tutor
    # ---------------------------------------------------------

    async def complete_booking(
        self,
        user: User,
        booking_id: uuid.UUID,
    ) -> BookingResponse:
        tutor = await self._get_verified_tutor(user)

        booking = await self.bookings.get_by_id_for_update(booking_id)

        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        if booking.tutor_profile_id != tutor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this booking.",
            )

        if booking.status != BookingStatus.CONFIRMED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only confirmed bookings can be marked completed.",
            )

        now = datetime.now(timezone.utc)

        if booking.end_at > now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A lesson cannot be marked completed before its scheduled end time."
                ),
            )

        try:
            booking.status = BookingStatus.AWAITING_LEARNER_ACKNOWLEDGEMENT
            booking.tutor_completed_at = now
            booking.acknowledgement_deadline_at = now + timedelta(hours=48)

            booking.acknowledgement_reminder_sent_at = None
            booking.admin_review_required_at = None
            booking.admin_reviewed_at = None
            booking.admin_reviewed_by_user_id = None
            booking.admin_review_notes = None

            # completed_at remains unset until learner acknowledgement.

            notifications = NotificationService(self.db)

            await notifications.create(
                user_id=booking.requester_user_id,
                notification_type=(NotificationType.SESSION_AWAITING_ACKNOWLEDGEMENT),
                title="Please confirm your tutoring session",
                message=(
                    "Your tutor has marked the lesson as completed. "
                    "Please confirm whether the session took place. "
                    "You have 48 hours to acknowledge it."
                ),
                data={
                    "booking_id": str(booking.id),
                    "tutoring_request_id": str(booking.tutoring_request_id),
                    "acknowledgement_deadline_at": (
                        booking.acknowledgement_deadline_at.isoformat()
                    ),
                },
            )

            await self.bookings.commit()
            await self.db.refresh(booking)

            return BookingResponse.model_validate(booking)

        except Exception:
            await self.bookings.rollback()
            raise

    # ---------------------------------------------------------
    # Dispute completion - Parent / Adult learner
    # ---------------------------------------------------------

    async def dispute_completion(
        self,
        user: User,
        booking_id: uuid.UUID,
        reason: str,
    ) -> BookingResponse:
        booking = await self.bookings.get_by_id_for_update(booking_id)

        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        if booking.requester_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the requester can dispute this session.",
            )

        if booking.status != (BookingStatus.AWAITING_LEARNER_ACKNOWLEDGEMENT):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("Only a session awaiting acknowledgement can be disputed."),
            )

        now = datetime.now(timezone.utc)

        try:
            booking.status = BookingStatus.DISPUTED
            booking.disputed_at = now
            booking.dispute_reason = reason
            booking.admin_review_required_at = now

            # A disputed booking must not become payout-eligible
            # until the dispute has been reviewed and resolved.

            await self.bookings.commit()
            await self.db.refresh(booking)

            return BookingResponse.model_validate(booking)

        except Exception:
            await self.bookings.rollback()
            raise

    # ---------------------------------------------------------
    # Acknowledge completion - Parent / Adult learner
    # ---------------------------------------------------------

    async def acknowledge_completion(
        self,
        user: User,
        booking_id: uuid.UUID,
    ) -> BookingResponse:
        booking = await self.bookings.get_by_id_for_update(booking_id)

        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        if booking.requester_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot acknowledge this session.",
            )

        if booking.status != (BookingStatus.AWAITING_LEARNER_ACKNOWLEDGEMENT):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("This session is not awaiting your acknowledgement."),
            )

        now = datetime.now(timezone.utc)

        try:
            booking.learner_acknowledged_at = now
            booking.completed_at = now
            booking.status = BookingStatus.COMPLETED

            notifications = NotificationService(self.db)

            tutor_user_id = await self._get_booking_tutor_user_id(booking)

            if tutor_user_id is not None:
                await notifications.create(
                    user_id=tutor_user_id,
                    notification_type=(NotificationType.SESSION_ACKNOWLEDGED),
                    title="Session completion acknowledged",
                    message=(
                        "The learner or parent has acknowledged the "
                        "completed session. It can now proceed through "
                        "the payment eligibility checks."
                    ),
                    data={
                        "booking_id": str(booking.id),
                        "tutoring_request_id": str(booking.tutoring_request_id),
                    },
                )

            await self.bookings.commit()
            await self.db.refresh(booking)

            return BookingResponse.model_validate(booking)

        except Exception:
            await self.bookings.rollback()
            raise
