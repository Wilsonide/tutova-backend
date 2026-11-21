import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.domain.authentication.models.user import User, UserRole, UserStatus
from app.domain.progress_reports.models.progress_report import ProgressReport, ProgressReportAuthor, ProgressReportReviewStatus
from app.domain.progress_reports.schemas.progress_report import ProgressReportCreate, ProgressReportReview
from app.domain.session_bookings.models.lesson_booking import BookingStatus, LessonBooking
from app.domain.notifications.models.notification import NotificationType
from app.domain.notifications.services.notification_service import NotificationService


class ProgressReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit(self, user: User, booking_id: uuid.UUID, payload: ProgressReportCreate):
        booking = await self.db.scalar(select(LessonBooking).where(LessonBooking.id == booking_id).with_for_update())
        if booking is None:
            raise HTTPException(404, "Lesson booking not found.")
        if booking.status not in {BookingStatus.AWAITING_LEARNER_ACKNOWLEDGEMENT, BookingStatus.DISPUTED, BookingStatus.COMPLETED}:
            raise HTTPException(409, "Progress reports can be submitted after the tutor marks the lesson completed.")
        if user.role == UserRole.TUTOR:
            author_type = ProgressReportAuthor.TUTOR
            from app.domain.tutors.models.tutor_profile import TutorProfile
            tutor_id = await self.db.scalar(select(TutorProfile.id).where(TutorProfile.user_id == user.id))
            if tutor_id is None or tutor_id != booking.tutor_profile_id:
                raise HTTPException(403, "You are not the tutor assigned to this lesson.")
        elif user.role in {UserRole.PARENT, UserRole.ADULT_LEARNER}:
            author_type = ProgressReportAuthor.LEARNER
            if booking.requester_user_id != user.id:
                raise HTTPException(403, "You are not authorised to report on this lesson.")
        else:
            raise HTTPException(403, "Only the tutor and learner can submit progress reports.")

        existing = await self.db.scalar(select(ProgressReport).where(ProgressReport.booking_id == booking.id, ProgressReport.author_user_id == user.id))
        if existing:
            raise HTTPException(409, "You have already submitted a report for this lesson.")
        report = ProgressReport(booking_id=booking.id, author_user_id=user.id, author_type=author_type, **payload.model_dump())
        self.db.add(report)
        has_issue = payload.issue_reported or not payload.attendance_confirmed
        if has_issue:
            booking.status = BookingStatus.DISPUTED
            booking.disputed_at = datetime.now(timezone.utc)
            booking.dispute_reason = (payload.issue_details or payload.feedback or "Lesson attendance was not confirmed")[:2000]
            booking.admin_review_required_at = booking.disputed_at
        admins = list((await self.db.scalars(select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]), User.status == UserStatus.ACTIVE))).all())
        notifications = NotificationService(self.db)
        for admin in admins:
            await notifications.create(admin.id, NotificationType.PROGRESS_REPORT_SUBMITTED, "New lesson progress report", "A lesson progress report has been submitted and is ready for admin review.", {"booking_id": str(booking.id), "report_id": str(report.id)})
        if has_issue:
            for admin in admins:
                await notifications.create(admin.id, NotificationType.SESSION_DISPUTED, "Lesson issue reported", "A learner or tutor has reported an issue with a lesson. Review the booking and reports.", {"booking_id": str(booking.id), "report_id": str(report.id)})
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def list_for_booking(self, user: User, booking_id: uuid.UUID):
        booking = await self.db.get(LessonBooking, booking_id)
        if booking is None:
            raise HTTPException(404, "Lesson booking not found.")
        if user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            if user.role == UserRole.TUTOR:
                from app.domain.tutors.models.tutor_profile import TutorProfile
                tutor_id = await self.db.scalar(select(TutorProfile.id).where(TutorProfile.user_id == user.id))
                allowed = tutor_id == booking.tutor_profile_id
            else:
                allowed = booking.requester_user_id == user.id
            if not allowed:
                raise HTTPException(403, "You cannot view reports for this lesson.")
        return list((await self.db.scalars(select(ProgressReport).where(ProgressReport.booking_id == booking_id).order_by(ProgressReport.created_at.asc()))).all())

    async def list_admin(self, status_filter: ProgressReportReviewStatus | None = None):
        query = select(ProgressReport).options(selectinload(ProgressReport.booking), selectinload(ProgressReport.author)).order_by(ProgressReport.created_at.desc())
        if status_filter:
            query = query.where(ProgressReport.review_status == status_filter)
        return list((await self.db.scalars(query)).all())

    async def review(self, admin: User, report_id: uuid.UUID, payload: ProgressReportReview):
        report = await self.db.scalar(select(ProgressReport).where(ProgressReport.id == report_id).with_for_update())
        if report is None:
            raise HTTPException(404, "Progress report not found.")
        report.review_status = payload.review_status
        report.admin_reviewed_by_user_id = admin.id
        report.admin_reviewed_at = datetime.now(timezone.utc)
        report.admin_review_notes = payload.admin_review_notes
        await self.db.commit()
        await self.db.refresh(report)
        return report
