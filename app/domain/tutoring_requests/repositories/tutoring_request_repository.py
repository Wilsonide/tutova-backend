import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.authentication.models.user import (
    User,
    UserRole,
    UserStatus,
)
from app.domain.tutoring_requests.models.tutor_request_response import (
    TutorRequestResponse,
    TutorResponseDecision,
)
from app.domain.tutoring_requests.models.tutoring_request import (
    TutoringRequest,
    TutoringRequestStatus,
)
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.subjects.models.subject import Subject
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)


class TutoringRequestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        request: TutoringRequest,
    ) -> TutoringRequest:
        self.db.add(request)
        await self.db.flush()
        return request

    async def get_by_id(
        self,
        request_id: uuid.UUID,
    ) -> TutoringRequest | None:
        result = await self.db.execute(
            select(TutoringRequest).where(TutoringRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(
        self,
        request_id: uuid.UUID,
    ) -> TutoringRequest | None:
        result = await self.db.execute(
            select(TutoringRequest)
            .where(TutoringRequest.id == request_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_for_requester(
        self,
        requester_user_id: uuid.UUID,
    ) -> list[TutoringRequest]:
        result = await self.db.execute(
            select(TutoringRequest)
            .where(TutoringRequest.requester_user_id == requester_user_id)
            .order_by(TutoringRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_tutor(
        self,
        tutor_profile_id: uuid.UUID,
        limit: int = 50,
    ) -> list[TutoringRequest]:
        declined_request_ids = select(TutorRequestResponse.tutoring_request_id).where(
            TutorRequestResponse.tutor_profile_id == tutor_profile_id,
            TutorRequestResponse.decision == TutorResponseDecision.DECLINED,
        )

        # Generic requests are visible to eligible tutors until they respond.
        # Direct requests are visible only to the tutor selected by the learner.
        open_generic_requests = and_(
            TutoringRequest.status == TutoringRequestStatus.OPEN,
            TutoringRequest.selected_tutor_id.is_(None),
            TutoringRequest.id.not_in(declined_request_ids),
        )
        open_direct_requests = and_(
            TutoringRequest.status == TutoringRequestStatus.OPEN,
            TutoringRequest.selected_tutor_id == tutor_profile_id,
        )

        accepted_requests = and_(
            TutoringRequest.status == TutoringRequestStatus.ACCEPTED,
            TutoringRequest.assigned_tutor_id == tutor_profile_id,
        )

        result = await self.db.execute(
            select(TutoringRequest)
            .options(
                selectinload(TutoringRequest.requester),
                selectinload(TutoringRequest.subject),
                selectinload(TutoringRequest.location),
            )
            .where(
                or_(
                    open_generic_requests,
                    open_direct_requests,
                    accepted_requests,
                )
            )
            .order_by(TutoringRequest.created_at.desc())
            .limit(limit)
        )

        return list(result.scalars().all())

    async def list_discoverable_tutors(
        self,
        *,
        subject_id: uuid.UUID,
        tutoring_mode: str,
        selected_tutor_id: uuid.UUID | None = None,
    ) -> list[tuple[TutorProfile, User]]:
        """
        Return active, verified tutors with their public user information.

        Subject and teaching-mode filtering is pushed into SQL; the service
        computes the location match level from the already-loaded locations.
        """

        stmt = (
            select(TutorProfile, User)
            .join(
                User,
                TutorProfile.user_id == User.id,
            )
            .join(
                TutorVerification,
                TutorVerification.tutor_user_id == User.id,
            )
            .options(
                selectinload(TutorProfile.subjects),
                selectinload(TutorProfile.locations),
            )
            .where(
                User.role == UserRole.TUTOR,
                User.status == UserStatus.ACTIVE,
                TutorVerification.status == VerificationStatus.APPROVED,
                TutorProfile.subjects.any(
                    Subject.id == subject_id
                ),
                TutorProfile.tutoring_modes.contains([tutoring_mode]),
            )
        )
        if selected_tutor_id is not None:
            stmt = stmt.where(TutorProfile.id == selected_tutor_id)

        return list((await self.db.execute(stmt)).unique().all())

    async def get_tutor_response(
        self,
        request_id: uuid.UUID,
        tutor_profile_id: uuid.UUID,
    ) -> TutorRequestResponse | None:
        result = await self.db.execute(
            select(TutorRequestResponse).where(
                TutorRequestResponse.tutoring_request_id == request_id,
                TutorRequestResponse.tutor_profile_id == tutor_profile_id,
            )
        )

        return result.scalar_one_or_none()

    async def create_tutor_response(
        self,
        response: TutorRequestResponse,
    ) -> TutorRequestResponse:
        self.db.add(response)
        await self.db.flush()
        return response

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()
