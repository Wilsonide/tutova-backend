import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.domain.authentication.models.user import User, UserRole
from app.domain.agreements.models.tutoring_agreement import TutoringAgreement, AgreementStatus
from app.domain.agreements.schemas.agreement import AgreementChangeRequest, AgreementLearnerDecision
from app.domain.notifications.models.notification import NotificationType
from app.domain.notifications.services.notification_service import NotificationService
from app.domain.payments.models.payment import Payment, PaymentStatus
from app.domain.session_bookings.models.lesson_booking import LessonBooking, BookingStatus
from app.domain.session_bookings.repositories.booking_repository import BookingRepository
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.tutoring_requests.models.tutoring_request import TutoringRequest, TutoringMode

class AgreementService:
    def __init__(self, db: AsyncSession): self.db=db

    @staticmethod
    def _snapshot(booking: LessonBooking) -> dict:
        return {
            "start_at": booking.start_at.isoformat(), "end_at": booking.end_at.isoformat(),
            "duration_minutes": booking.duration_minutes, "location_id": str(booking.location_id) if booking.location_id else None,
            "meeting_link": booking.meeting_link, "lesson_notes": booking.lesson_notes,
            "monthly_fee": str(booking.monthly_fee) if booking.monthly_fee is not None else None,
            "gross_amount_minor": booking.gross_amount_minor, "currency": booking.currency,
        }

    async def create_for_booking(self, booking: LessonBooking) -> TutoringAgreement:
        existing = await self.db.scalar(
            select(TutoringAgreement).where(TutoringAgreement.booking_id == booking.id)
        )
        if existing:
            return existing
        terms = self._snapshot(booking)
        from app.domain.locations.models.location import Location
        from app.domain.subjects.models.subject import Subject
        from app.domain.session_bookings.models.monthly_arrangement import MonthlyTutoringArrangement
        request = await self.db.get(TutoringRequest, booking.tutoring_request_id)
        if request:
            subject = await self.db.get(Subject, request.subject_id)
            terms["subject"] = subject.name if subject else "Tutoring subject"
            terms["tutoring_mode"] = request.tutoring_mode.value
        if booking.location_id:
            venue = await self.db.get(Location, booking.location_id)
            terms["venue"] = venue.name if venue else "Venue to be confirmed"
        arrangement = (
            await self.db.get(MonthlyTutoringArrangement, booking.monthly_arrangement_id)
            if booking.monthly_arrangement_id else None
        )
        if arrangement:
            terms.update({
                "duration_months": arrangement.duration_months,
                "commission_bps": arrangement.commission_bps,
                "platform_fee_minor": arrangement.platform_fee_minor,
                "tutor_commission_minor": arrangement.tutor_commission_minor,
                "learner_fee_minor": arrangement.learner_fee_minor,
                "tutor_earning_minor": arrangement.tutor_earning_minor,
                "learner_total_minor": arrangement.monthly_fee_minor * arrangement.duration_months + arrangement.learner_fee_minor,
                "commission_schedule": arrangement.commission_schedule or [],
            })
        agreement = TutoringAgreement(
            booking_id=booking.id,
            tutoring_request_id=booking.tutoring_request_id,
            requester_user_id=booking.requester_user_id,
            tutor_profile_id=booking.tutor_profile_id,
            status=AgreementStatus.PENDING_TUTOR_REVIEW,
            revision=1,
            terms=terms,
            revision_history=[],
        )
        self.db.add(agreement)
        await self.db.flush()
        return agreement

    async def list_mine(self, user: User):
        query=select(TutoringAgreement).order_by(TutoringAgreement.created_at.desc())
        if user.role == UserRole.TUTOR:
            query=query.where(TutoringAgreement.tutor_profile_id.in_(select(TutorProfile.id).where(TutorProfile.user_id==user.id)))
        elif user.role in {UserRole.PARENT, UserRole.ADULT_LEARNER}:
            query=query.where(TutoringAgreement.requester_user_id==user.id)
        elif user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(403,"You cannot view tutoring agreements.")
        return list((await self.db.scalars(query)).all())

    async def tutor_accept(self, user: User, agreement_id: uuid.UUID):
        tutor_id=await self.db.scalar(select(TutorProfile.id).where(TutorProfile.user_id==user.id))
        agreement=await self.db.scalar(select(TutoringAgreement).where(TutoringAgreement.id==agreement_id).with_for_update())
        if agreement is None: raise HTTPException(404,"Agreement not found.")
        if tutor_id is None or agreement.tutor_profile_id!=tutor_id: raise HTTPException(403,"You are not the tutor for this agreement.")
        if agreement.status not in {AgreementStatus.PENDING_TUTOR_REVIEW, AgreementStatus.CHANGES_REQUESTED}: raise HTTPException(409,"This agreement is not awaiting tutor review.")
        agreement.status=AgreementStatus.PENDING_LEARNER_APPROVAL; agreement.tutor_reviewed_at=datetime.now(timezone.utc)
        await NotificationService(self.db).create(agreement.requester_user_id, NotificationType.AGREEMENT_READY_FOR_LEARNER,"Tutoring agreement ready for review","Your tutor has reviewed the proposed terms. Review and accept the agreement to confirm the booking.",{"agreement_id":str(agreement.id),"booking_id":str(agreement.booking_id)})
        await self.db.commit(); await self.db.refresh(agreement); return agreement

    async def tutor_request_changes(self,user:User,agreement_id:uuid.UUID,payload:AgreementChangeRequest):
        tutor_id=await self.db.scalar(select(TutorProfile.id).where(TutorProfile.user_id==user.id))
        agreement=await self.db.scalar(select(TutoringAgreement).where(TutoringAgreement.id==agreement_id).with_for_update())
        if agreement is None: raise HTTPException(404,"Agreement not found.")
        if tutor_id is None or agreement.tutor_profile_id!=tutor_id: raise HTTPException(403,"You are not the tutor for this agreement.")
        if agreement.status not in {AgreementStatus.PENDING_TUTOR_REVIEW,AgreementStatus.CHANGES_REQUESTED}: raise HTTPException(409,"This agreement cannot be revised now.")
        booking=await self.db.scalar(select(LessonBooking).where(LessonBooking.id==agreement.booking_id).with_for_update())
        if booking is None:
            raise HTTPException(404,"The booking linked to this agreement no longer exists.")
        request=await self.db.get(TutoringRequest,agreement.tutoring_request_id)
        start=payload.start_at
        if start.tzinfo is None or start.utcoffset() is None: raise HTTPException(422,"The proposed start time must include a timezone.")
        start=start.astimezone(timezone.utc); end=start + timedelta(minutes=payload.duration_minutes)
        if start<=datetime.now(timezone.utc): raise HTTPException(422,"The proposed lesson time must be in the future.")
        if request and request.tutoring_mode in {TutoringMode.IN_PERSON, TutoringMode.HYBRID}:
            if payload.location_id is None:
                raise HTTPException(422,"A venue is required for in-person or hybrid tutoring.")
            from app.domain.locations.models.location import Location
            location = await self.db.get(Location, payload.location_id)
            if location is None or not location.is_active:
                raise HTTPException(422,"The proposed venue is unavailable.")
            tutor_profile = await self.db.scalar(select(TutorProfile).options(selectinload(TutorProfile.locations)).where(TutorProfile.id == booking.tutor_profile_id))
            from app.domain.tutoring_requests.services.tutoring_request_service import TutoringRequestService
            if tutor_profile is None or not await TutoringRequestService(self.db)._tutor_serves_location(tutor_profile, payload.location_id):
                raise HTTPException(422,"The proposed venue is outside the tutor's registered service area.")
        if request and request.tutoring_mode in {TutoringMode.ONLINE, TutoringMode.HYBRID} and payload.meeting_link and not payload.meeting_link.startswith(("https://", "http://")):
            raise HTTPException(422,"The meeting link must begin with http:// or https://.")
        repo=BookingRepository(self.db)
        await repo.lock_requester(booking.requester_user_id); await repo.lock_tutor(booking.tutor_profile_id)
        if await repo.has_tutor_conflict(booking.tutor_profile_id,start,end,exclude_booking_id=booking.id): raise HTTPException(409,"Tutor is unavailable at the proposed time.")
        if await repo.has_requester_conflict(booking.requester_user_id,start,end,exclude_booking_id=booking.id): raise HTTPException(409,"Learner has another booking at the proposed time.")
        old_terms=agreement.terms
        booking.start_at=start; booking.end_at=end; booking.duration_minutes=payload.duration_minutes
        booking.meeting_link=payload.meeting_link if request and request.tutoring_mode in {TutoringMode.ONLINE, TutoringMode.HYBRID} else None
        booking.location_id=payload.location_id if request and request.tutoring_mode in {TutoringMode.IN_PERSON, TutoringMode.HYBRID} else None
        booking.lesson_notes=payload.lesson_notes
        from app.domain.locations.models.location import Location
        venue = await self.db.get(Location, booking.location_id) if booking.location_id else None
        new_terms = self._snapshot(booking)
        new_terms["venue"] = venue.name if venue else ("Online lesson" if booking.meeting_link else "Venue to be confirmed")
        agreement.revision += 1; agreement.revision_history=(agreement.revision_history or []) + [{"revision":agreement.revision-1,"terms":old_terms,"changed_at":datetime.now(timezone.utc).isoformat(),"changed_by":str(user.id),"reason":payload.notes}]
        agreement.terms=new_terms; agreement.tutor_notes=payload.notes; agreement.tutor_reviewed_at=datetime.now(timezone.utc); agreement.status=AgreementStatus.PENDING_LEARNER_APPROVAL
        await NotificationService(self.db).create(agreement.requester_user_id,NotificationType.AGREEMENT_READY_FOR_LEARNER,"Tutor proposed revised agreement terms","Your tutor proposed changes to the lesson schedule or arrangement. Review the updated agreement.",{"agreement_id":str(agreement.id),"booking_id":str(booking.id)})
        await self.db.commit(); await self.db.refresh(agreement); return agreement

    async def learner_decide(self,user:User,agreement_id:uuid.UUID,payload:AgreementLearnerDecision):
        agreement=await self.db.scalar(select(TutoringAgreement).where(TutoringAgreement.id==agreement_id).with_for_update())
        if agreement is None: raise HTTPException(404,"Agreement not found.")
        if agreement.requester_user_id!=user.id: raise HTTPException(403,"You are not authorised to decide on this agreement.")
        if agreement.status!=AgreementStatus.PENDING_LEARNER_APPROVAL: raise HTTPException(409,"This agreement is not awaiting your approval.")
        booking=await self.db.scalar(select(LessonBooking).where(LessonBooking.id==agreement.booking_id).with_for_update())
        if booking is None:
            raise HTTPException(404,"The booking linked to this agreement no longer exists.")
        notifications = NotificationService(self.db)
        tutor_profile = await self.db.get(TutorProfile, agreement.tutor_profile_id)
        if payload.decision=="CANCEL":
            agreement.status=AgreementStatus.CANCELLED; agreement.learner_notes=payload.notes
            booking.status=BookingStatus.CANCELLED; booking.cancelled_at=datetime.now(timezone.utc); booking.cancellation_reason=payload.notes or "Learner declined the tutoring agreement."
            paid_payment = await self.db.scalar(select(Payment.id).where(Payment.booking_id == booking.id, Payment.status == PaymentStatus.PAID))
            if paid_payment is not None:
                from app.domain.authentication.models.user import UserRole, UserStatus
                admins = list((await self.db.scalars(select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]), User.status == UserStatus.ACTIVE))).all())
                for admin in admins:
                    await notifications.create(admin.id, NotificationType.ADMIN_NEW_TUTORING_REQUEST, "Agreement declined after payment — refund review required", "The learner declined the tutoring agreement after payment. Review the payment and determine the appropriate refund action.", {"agreement_id": str(agreement.id), "booking_id": str(booking.id), "payment_id": str(paid_payment)})
        else:
            if booking.start_at <= datetime.now(timezone.utc):
                raise HTTPException(409,"This proposed lesson time has passed. Ask the tutor to revise the agreement.")
            agreement.status=AgreementStatus.SIGNED; agreement.learner_accepted_at=datetime.now(timezone.utc); agreement.learner_notes=payload.notes
            booking.status=BookingStatus.CONFIRMED; booking.confirmed_at=datetime.now(timezone.utc)
            if tutor_profile:
                await notifications.create(tutor_profile.user_id,NotificationType.AGREEMENT_SIGNED,"Tutoring agreement accepted","The learner accepted the tutoring agreement. The booking is now confirmed.",{"agreement_id":str(agreement.id),"booking_id":str(booking.id)})
        await self.db.commit(); await self.db.refresh(agreement); return agreement
