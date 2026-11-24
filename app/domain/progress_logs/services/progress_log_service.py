import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.models.user import User, UserRole, UserStatus
from app.domain.notifications.models.notification import NotificationType
from app.domain.notifications.services.notification_service import NotificationService
from app.domain.progress_logs.models.progress_log_entry import (
    ProgressLogEntry,
    ProgressLogEntryType,
    ProgressLogReviewStatus,
)
from app.domain.progress_logs.repositories.progress_log_repository import ProgressLogRepository
from app.domain.progress_logs.schemas.progress_log import ProgressLogCreate, ProgressLogReview
from app.domain.tutoring_requests.models.tutoring_request import (
    TutoringRequest,
    TutoringRequestStatus,
)
from app.domain.tutors.models.tutor_profile import TutorProfile


class ProgressLogService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ProgressLogRepository(db)
        self.notifications = NotificationService(db)

    async def _get_request(self, request_id: uuid.UUID) -> TutoringRequest:
        request = await self.db.get(TutoringRequest, request_id)
        if request is None:
            raise HTTPException(404, "Tutoring relationship not found.")
        if request.assigned_tutor_id is None:
            raise HTTPException(409, "This tutoring request does not have an assigned tutor.")
        return request

    async def _participant_type(self, user: User, request: TutoringRequest) -> str:
        if user.role in {UserRole.PARENT, UserRole.ADULT_LEARNER}:
            if request.requester_user_id != user.id:
                raise HTTPException(403, "You are not a participant in this tutoring progress log.")
            return "LEARNER"

        if user.role == UserRole.TUTOR:
            tutor_profile_id = await self.db.scalar(
                select(TutorProfile.id).where(TutorProfile.user_id == user.id)
            )
            if tutor_profile_id is None or tutor_profile_id != request.assigned_tutor_id:
                raise HTTPException(403, "You are not the tutor assigned to this tutoring relationship.")
            return "TUTOR"

        raise HTTPException(403, "Only the assigned tutor and learner can post progress updates.")

    async def list_rooms(self, user: User):
        query = (
            select(TutoringRequest)
            .options(
                selectinload(TutoringRequest.requester),
                selectinload(TutoringRequest.learner),
                selectinload(TutoringRequest.subject),
                selectinload(TutoringRequest.assigned_tutor).selectinload(TutorProfile.user),
            )
            .where(
                TutoringRequest.status == TutoringRequestStatus.ACCEPTED,
                TutoringRequest.assigned_tutor_id.is_not(None),
            )
            .order_by(TutoringRequest.updated_at.desc())
        )

        if user.role in {UserRole.PARENT, UserRole.ADULT_LEARNER}:
            query = query.where(TutoringRequest.requester_user_id == user.id)
        elif user.role == UserRole.TUTOR:
            tutor_profile_id = await self.db.scalar(
                select(TutorProfile.id).where(TutorProfile.user_id == user.id)
            )
            if tutor_profile_id is None:
                return []
            query = query.where(TutoringRequest.assigned_tutor_id == tutor_profile_id)
        elif user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(403, "You cannot view tutoring progress rooms.")

        requests = list((await self.db.scalars(query)).all())
        rooms = []
        for request in requests:
            requester = request.requester
            tutor_profile = request.assigned_tutor
            tutor_user = tutor_profile.user if tutor_profile else None
            learner = request.learner
            requester_name = (
                f"{requester.first_name} {requester.last_name}".strip()
                if requester else "Learner"
            )
            tutor_name = (
                f"{tutor_user.first_name} {tutor_user.last_name}".strip()
                if tutor_user else "Tutor"
            )
            learner_name = (
                f"{learner.first_name} {learner.last_name}".strip()
                if learner else (
                    requester_name if requester and requester.role == UserRole.ADULT_LEARNER
                    else None
                )
            )
            rooms.append({
                "id": request.id,
                "status": request.status.value,
                "assigned_tutor_id": request.assigned_tutor_id,
                "created_at": request.created_at,
                "tutor_name": tutor_name,
                "requester_name": requester_name,
                "requester_role": requester.role.value if requester else "PARENT",
                "learner_name": learner_name,
                "subject_name": request.subject.name if request.subject else "Tutoring",
                "tutoring_mode": request.tutoring_mode.value,
            })
        return rooms

    async def create(
        self,
        user: User,
        request_id: uuid.UUID,
        payload: ProgressLogCreate,
    ) -> ProgressLogEntry:
        request = await self._get_request(request_id)
        if request.status != TutoringRequestStatus.ACCEPTED:
            raise HTTPException(409, "New progress updates are available while the tutoring request is active.")
        author_type = await self._participant_type(user, request)
        is_concern = payload.entry_type == ProgressLogEntryType.CONCERN

        entry = ProgressLogEntry(
            tutoring_request_id=request.id,
            author_user_id=user.id,
            author_type=author_type,
            entry_type=payload.entry_type,
            log_date=datetime.now(timezone(timedelta(hours=1))).date(),
            message=payload.message.strip(),
            review_status=(
                ProgressLogReviewStatus.FLAGGED if is_concern else ProgressLogReviewStatus.PENDING
            ),
        )

        try:
            await self.repository.create(entry)
            await self.db.flush()

            # Notify the other participant that a new update has been posted.
            if author_type == "TUTOR":
                recipient_id = request.requester_user_id
            else:
                recipient_id = await self.db.scalar(
                    select(TutorProfile.user_id).where(TutorProfile.id == request.assigned_tutor_id)
                )

            if recipient_id is not None:
                await self.notifications.create(
                    user_id=recipient_id,
                    notification_type=NotificationType.PROGRESS_LOG_ENTRY,
                    title="New tutoring progress update",
                    message=f"{user.first_name} added an update to your Tutova learning log.",
                    data={"tutoring_request_id": str(request.id), "entry_id": str(entry.id)},
                )

            # Concerns are escalated to administrators immediately.
            if is_concern:
                admins = await self.db.scalars(
                    select(User.id).where(
                        User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]),
                        User.status == UserStatus.ACTIVE,
                    )
                )
                for admin_id in admins:
                    await self.notifications.create(
                        user_id=admin_id,
                        notification_type=NotificationType.PROGRESS_LOG_CONCERN,
                        title="Progress log concern requires review",
                        message="A concern has been recorded in a tutoring progress log.",
                        data={"tutoring_request_id": str(request.id), "entry_id": str(entry.id)},
                    )

            await self.db.commit()
            return await self.repository.get_by_id_with_author(entry.id)
        except Exception:
            await self.db.rollback()
            raise

    async def list_for_request(self, user: User, request_id: uuid.UUID) -> list[ProgressLogEntry]:
        request = await self._get_request(request_id)
        if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            pass
        else:
            await self._participant_type(user, request)
        return await self.repository.list_for_request(request_id)

    async def list_admin(
        self,
        status_filter: ProgressLogReviewStatus | None = None,
        limit: int = 200,
    ) -> list[ProgressLogEntry]:
        return await self.repository.list_admin(status_filter, limit)

    async def review(
        self,
        admin: User,
        entry_id: uuid.UUID,
        payload: ProgressLogReview,
    ) -> ProgressLogEntry:
        entry = await self.repository.get_for_update(entry_id)
        if entry is None:
            raise HTTPException(404, "Progress log entry not found.")
        entry.review_status = payload.review_status
        entry.admin_reviewed_by_user_id = admin.id
        entry.admin_reviewed_at = datetime.now(timezone.utc)
        entry.admin_review_notes = payload.admin_review_notes
        try:
            await self.db.commit()
            return await self.repository.get_by_id_with_author(entry.id)
        except Exception:
            await self.db.rollback()
            raise
