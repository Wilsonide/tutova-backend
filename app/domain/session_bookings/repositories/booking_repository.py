import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.models.user import User, UserRole, UserStatus
from app.domain.session_bookings.models.lesson_booking import (
    BookingStatus,
    LessonBooking,
)
from app.domain.tutors.models.tutor_profile import TutorProfile

ACTIVE_BOOKING_STATUSES = (
    BookingStatus.PENDING_TUTOR_CONFIRMATION,
    BookingStatus.PENDING_CONFIRMATION,  # Legacy bookings
    BookingStatus.CONFIRMED,
)


class BookingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def lock_tutor(self, tutor_profile_id: uuid.UUID):
        result = await self.db.execute(
            select(TutorProfile)
            .where(TutorProfile.id == tutor_profile_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def lock_requester(self, requester_user_id: uuid.UUID):
        """
        Serializes booking creation for the same requester.

        This helps prevent a requester from creating overlapping bookings
        with different tutors concurrently.
        """
        result = await self.db.execute(
            select(User).where(User.id == requester_user_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def create(self, booking: LessonBooking):
        self.db.add(booking)
        await self.db.flush()
        await self.db.refresh(booking)
        return booking

    async def get_by_id(self, booking_id: uuid.UUID):
        result = await self.db.execute(
            select(LessonBooking).where(LessonBooking.id == booking_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, booking_id: uuid.UUID):
        result = await self.db.execute(
            select(LessonBooking)
            .where(LessonBooking.id == booking_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def has_tutor_conflict(
        self,
        tutor_profile_id: uuid.UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_booking_id: uuid.UUID | None = None,
    ) -> bool:
        statement = select(LessonBooking.id).where(
            LessonBooking.tutor_profile_id == tutor_profile_id,
            LessonBooking.status.in_(ACTIVE_BOOKING_STATUSES),
            LessonBooking.start_at < end_at,
            LessonBooking.end_at > start_at,
        )

        if exclude_booking_id is not None:
            statement = statement.where(LessonBooking.id != exclude_booking_id)

        result = await self.db.execute(statement.limit(1))
        return result.scalar_one_or_none() is not None

    async def has_requester_conflict(
        self,
        requester_user_id: uuid.UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_booking_id: uuid.UUID | None = None,
    ) -> bool:
        statement = select(LessonBooking.id).where(
            LessonBooking.requester_user_id == requester_user_id,
            LessonBooking.status.in_(ACTIVE_BOOKING_STATUSES),
            LessonBooking.start_at < end_at,
            LessonBooking.end_at > start_at,
        )

        if exclude_booking_id is not None:
            statement = statement.where(LessonBooking.id != exclude_booking_id)

        result = await self.db.execute(statement.limit(1))
        return result.scalar_one_or_none() is not None

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ):
        statement = (
            select(LessonBooking)
            .where(
                or_(
                    LessonBooking.requester_user_id == user_id,
                    LessonBooking.tutor_profile_id.in_(
                        select(TutorProfile.id).where(TutorProfile.user_id == user_id)
                    ),
                )
            )
            .order_by(LessonBooking.start_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(statement)
        return result.scalars().all()

    async def list_due_acknowledgement_reminders(
        self,
        reminder_cutoff: datetime,
        limit: int = 100,
    ) -> list[LessonBooking]:
        statement = (
            select(LessonBooking)
            .where(
                LessonBooking.status == BookingStatus.AWAITING_LEARNER_ACKNOWLEDGEMENT,
                LessonBooking.tutor_completed_at.is_not(None),
                LessonBooking.tutor_completed_at <= reminder_cutoff,
                LessonBooking.acknowledgement_reminder_sent_at.is_(None),
            )
            .order_by(LessonBooking.tutor_completed_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def list_due_admin_reviews(
        self,
        now: datetime,
        limit: int = 100,
    ) -> list[LessonBooking]:
        statement = (
            select(LessonBooking)
            .where(
                LessonBooking.admin_review_notification_sent_at.is_(None),
                or_(
                    # Disputes require immediate admin review.
                    LessonBooking.status == BookingStatus.DISPUTED,
                    # Unacknowledged sessions require review after deadline.
                    (
                        (
                            LessonBooking.status
                            == BookingStatus.AWAITING_LEARNER_ACKNOWLEDGEMENT
                        )
                        & (LessonBooking.acknowledgement_deadline_at.is_not(None))
                        & (LessonBooking.acknowledgement_deadline_at <= now)
                    ),
                ),
            )
            .order_by(LessonBooking.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def list_active_admin_user_ids(self) -> list[uuid.UUID]:
        result = await self.db.execute(
            select(User.id).where(
                User.role.in_(
                    [
                        UserRole.ADMIN,
                        UserRole.SUPER_ADMIN,
                    ]
                ),
                User.status == UserStatus.ACTIVE,
            )
        )

        return list(result.scalars().all())

    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()
