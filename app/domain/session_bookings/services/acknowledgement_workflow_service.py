from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notifications.models.notification import NotificationType
from app.domain.notifications.services.notification_service import (
    NotificationService,
)
from app.domain.session_bookings.models.lesson_booking import (
    BookingStatus,
)
from app.domain.session_bookings.repositories.booking_repository import (
    BookingRepository,
)


class AcknowledgementWorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.bookings = BookingRepository(db)
        self.notifications = NotificationService(db)

    async def process_deadlines(
        self,
        batch_size: int = 100,
        now: datetime | None = None,
    ) -> dict:
        """
        Process acknowledgement reminders and overdue admin reviews.

        This method does not commit per notification. Booking markers and
        notifications are persisted together in one transaction.
        """

        now = now or datetime.now(timezone.utc)

        reminder_cutoff = now - timedelta(hours=24)

        reminder_count = 0
        admin_review_count = 0

        try:
            # -------------------------------------------------
            # 24-hour learner acknowledgement reminders
            # -------------------------------------------------

            due_reminders = await self.bookings.list_due_acknowledgement_reminders(
                reminder_cutoff=reminder_cutoff,
                limit=batch_size,
            )

            for booking in due_reminders:
                # Recheck after acquiring the row lock.
                if (
                    booking.status != BookingStatus.AWAITING_LEARNER_ACKNOWLEDGEMENT
                    or booking.acknowledgement_reminder_sent_at is not None
                ):
                    continue

                await self.notifications.create(
                    user_id=booking.requester_user_id,
                    notification_type=(
                        NotificationType.SESSION_ACKNOWLEDGEMENT_REMINDER
                    ),
                    title="Reminder: acknowledge your tutoring session",
                    message=(
                        "Your tutor marked this session as completed. "
                        "Please confirm whether the lesson took place. "
                        "Your acknowledgement is still pending."
                    ),
                    data={
                        "booking_id": str(booking.id),
                        "tutoring_request_id": str(booking.tutoring_request_id),
                        "acknowledgement_deadline_at": (
                            booking.acknowledgement_deadline_at.isoformat()
                            if booking.acknowledgement_deadline_at
                            else None
                        ),
                    },
                )

                booking.acknowledgement_reminder_sent_at = now
                reminder_count += 1

            # -------------------------------------------------
            # 48-hour overdue bookings and disputed bookings
            # -------------------------------------------------

            due_reviews = await self.bookings.list_due_admin_reviews(
                now=now,
                limit=batch_size,
            )

            admin_ids = await self.bookings.list_active_admin_user_ids()

            for booking in due_reviews:
                if booking.admin_review_notification_sent_at is not None:
                    continue

                if booking.status == BookingStatus.DISPUTED:
                    review_reason = (
                        "A learner or parent has disputed session completion."
                    )
                elif (
                    booking.status == BookingStatus.AWAITING_LEARNER_ACKNOWLEDGEMENT
                    and booking.acknowledgement_deadline_at is not None
                    and booking.acknowledgement_deadline_at <= now
                ):
                    review_reason = (
                        "The 48-hour learner acknowledgement deadline has passed."
                    )
                else:
                    continue

                if booking.admin_review_required_at is None:
                    booking.admin_review_required_at = now

                # If no active administrators exist, leave the notification
                # marker unset so a later scheduler run can retry.
                if not admin_ids:
                    continue

                for admin_id in admin_ids:
                    await self.notifications.create(
                        user_id=admin_id,
                        notification_type=(
                            NotificationType.SESSION_ACKNOWLEDGEMENT_OVERDUE_ADMIN_REVIEW
                            if booking.status
                            == BookingStatus.AWAITING_LEARNER_ACKNOWLEDGEMENT
                            else NotificationType.SESSION_DISPUTED
                        ),
                        title="Session requires administrative review",
                        message=review_reason,
                        data={
                            "booking_id": str(booking.id),
                            "tutoring_request_id": str(booking.tutoring_request_id),
                            "booking_status": booking.status.value,
                        },
                    )

                booking.admin_review_notification_sent_at = now
                admin_review_count += 1

            await self.db.commit()

            return {
                "reminders_sent": reminder_count,
                "admin_reviews_flagged": admin_review_count,
                "processed_at": now,
            }

        except Exception:
            await self.db.rollback()
            raise
