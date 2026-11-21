import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.authentication.models.user import User, UserRole, UserStatus
from app.domain.learners.models.learner_profile import LearnerProfile
from app.domain.locations.models.location import Location
from app.domain.notifications.models.notification import NotificationType
from app.domain.notifications.services.notification_service import (
    NotificationService,
)
from app.domain.parents.models.parent_profile import ParentProfile
from app.domain.subjects.models.subject import Subject
from app.domain.tutoring_requests.models.tutor_request_response import (
    TutorRequestResponse as TutorRequestResponseModel,
)
from app.domain.tutoring_requests.models.tutor_request_response import (
    TutorResponseDecision,
)
from app.domain.tutoring_requests.models.tutoring_request import (
    TutoringMode,
    TutoringRequest,
    TutoringRequestStatus,
)
from app.domain.tutoring_requests.repositories.tutoring_request_repository import (
    TutoringRequestRepository,
)
from app.domain.tutoring_requests.schemas.matching_tutor import (
    MatchingTutorResponse,
)
from app.domain.tutoring_requests.schemas.tutoring_request import (
    TutoringRequestCreate,
    TutoringRequestResponse,
    TutorMatchingRequestResponse,
    TutorRequestDecisionResult,
)
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)


def role_value(user: User) -> str:
    role = user.role
    return str(getattr(role, "value", role)).upper()


class TutoringRequestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.requests = TutoringRequestRepository(db)

    def _ensure_active_account(self, user: User) -> None:
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=403,
                detail="Your account is not active.",
            )

    async def _get_verified_tutor(self, user: User) -> TutorProfile:
        self._ensure_active_account(user)

        if role_value(user) != "TUTOR":
            raise HTTPException(
                status_code=403,
                detail="Only tutors can perform this action.",
            )

        result = await self.db.execute(
            select(TutorProfile)
            .options(
                selectinload(TutorProfile.subjects),
                selectinload(TutorProfile.locations),
            )
            .where(TutorProfile.user_id == user.id)
        )
        tutor = result.scalar_one_or_none()

        if tutor is None:
            raise HTTPException(
                status_code=404,
                detail="Tutor profile not found.",
            )

        verification_result = await self.db.execute(
            select(TutorVerification).where(
                TutorVerification.tutor_user_id == user.id,
                TutorVerification.status == VerificationStatus.APPROVED,
            )
        )

        if verification_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Tutor verification must be approved before "
                    "accessing tutoring requests."
                ),
            )

        return tutor

    async def _get_location_ancestor_ids(
        self,
        location_id: uuid.UUID,
    ) -> set[uuid.UUID]:
        """
        Return the selected location and all its active ancestors.

        Examples:
            Community -> LGA -> State
            Community -> City -> State
            LGA -> State
            City -> State

        This allows a tutor registered at a broader location level
        to serve requests made in a more specific location beneath it.
        """
        ancestors: set[uuid.UUID] = set()
        current_id: uuid.UUID | None = location_id

        while current_id is not None and current_id not in ancestors:
            result = await self.db.execute(
                select(Location).where(
                    Location.id == current_id,
                    Location.is_active.is_(True),
                )
            )
            location = result.scalar_one_or_none()

            if location is None:
                break

            ancestors.add(location.id)
            current_id = location.parent_id

        return ancestors

    async def _tutor_serves_location(
        self,
        tutor: TutorProfile,
        requested_location_id: uuid.UUID | None,
    ) -> bool:
        """
        A tutor serves a request when one of their registered locations
        is the requested location or an ancestor of that location.

        A tutor registered in an LGA therefore serves communities
        within that LGA. A tutor registered in a community does not
        automatically claim to serve the entire LGA.
        """
        if requested_location_id is None:
            return False

        tutor_location_ids = {
            location.id for location in tutor.locations if location.is_active
        }

        if not tutor_location_ids:
            return False

        requested_ancestors = await self._get_location_ancestor_ids(
            requested_location_id
        )

        return bool(tutor_location_ids.intersection(requested_ancestors))

    async def _get_selected_tutor(
        self,
        tutor_user_id: uuid.UUID,
        subject_id: uuid.UUID,
        tutoring_mode: TutoringMode,
        location_id: uuid.UUID | None,
    ) -> TutorProfile:
        """
        Resolve and validate a tutor selected by the requester.

        The submitted identifier is the tutor's User ID.
        The returned profile ID is stored on the tutoring request.
        """
        user_result = await self.db.execute(
            select(User).where(
                User.id == tutor_user_id,
                User.role == UserRole.TUTOR,
                User.status == UserStatus.ACTIVE,
            )
        )
        tutor_user = user_result.scalar_one_or_none()

        if tutor_user is None:
            raise HTTPException(
                status_code=422,
                detail="The selected tutor is unavailable.",
            )

        verification_result = await self.db.execute(
            select(TutorVerification).where(
                TutorVerification.tutor_user_id == tutor_user.id,
                TutorVerification.status == VerificationStatus.APPROVED,
            )
        )

        if verification_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=422,
                detail="The selected tutor is not verified.",
            )

        profile_result = await self.db.execute(
            select(TutorProfile)
            .options(
                selectinload(TutorProfile.subjects),
                selectinload(TutorProfile.locations),
            )
            .where(TutorProfile.user_id == tutor_user.id)
        )
        tutor = profile_result.scalar_one_or_none()

        if tutor is None:
            raise HTTPException(
                status_code=422,
                detail="The selected tutor profile is unavailable.",
            )

        if subject_id not in {subject.id for subject in tutor.subjects}:
            raise HTTPException(
                status_code=422,
                detail="The selected tutor is not registered to teach this subject.",
            )

        supported_modes = {
            str(getattr(mode, "value", mode)).upper()
            for mode in (tutor.tutoring_modes or [])
        }

        if tutoring_mode.value not in supported_modes:
            raise HTTPException(
                status_code=422,
                detail="The selected tutor does not support this tutoring mode.",
            )

        if tutoring_mode in {TutoringMode.IN_PERSON, TutoringMode.HYBRID}:
            if not await self._tutor_serves_location(tutor, location_id):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "The selected tutor does not serve the requested "
                        "location or its registered service area."
                    ),
                )

        return tutor

    async def _resolve_request_learner_profile(
        self,
        user: User,
        supplied_learner_id: uuid.UUID | None = None,
    ) -> uuid.UUID | None:
        """
        Parents can submit requests without a child LearnerProfile.
        Adult learners must have and use their own LearnerProfile.
        """
        role = role_value(user)

        if role == "PARENT":
            parent_result = await self.db.execute(
                select(ParentProfile).where(ParentProfile.user_id == user.id)
            )

            if parent_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Parent profile not found. Please complete your parent profile."
                    ),
                )

            return None

        if role == "ADULT_LEARNER":
            learner_result = await self.db.execute(
                select(LearnerProfile).where(LearnerProfile.user_id == user.id)
            )
            learner = learner_result.scalar_one_or_none()

            if learner is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Your learner profile was not found. "
                        "Please complete your learner profile before booking."
                    ),
                )

            if supplied_learner_id is not None and supplied_learner_id != learner.id:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "You can only request tutoring for your own learner profile."
                    ),
                )

            return learner.id

        raise HTTPException(
            status_code=403,
            detail=("Only parents and adult learners can create tutoring requests."),
        )

    async def create(
        self,
        user: User,
        data: TutoringRequestCreate,
    ) -> TutoringRequest:
        self._ensure_active_account(user)

        learner_profile_id = await self._resolve_request_learner_profile(
            user=user,
            supplied_learner_id=data.learner_profile_id,
        )

        subject_result = await self.db.execute(
            select(Subject).where(
                Subject.id == data.subject_id,
                Subject.is_active.is_(True),
            )
        )

        if subject_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=422,
                detail="The selected subject is unavailable.",
            )

        if data.tutoring_mode in {TutoringMode.IN_PERSON, TutoringMode.HYBRID}:
            location_result = await self.db.execute(
                select(Location).where(
                    Location.id == data.location_id,
                    Location.is_active.is_(True),
                )
            )

            if location_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=422,
                    detail="The selected location is unavailable.",
                )

        selected_tutor = None

        if data.selected_tutor_user_id is not None:
            selected_tutor = await self._get_selected_tutor(
                tutor_user_id=data.selected_tutor_user_id,
                subject_id=data.subject_id,
                tutoring_mode=data.tutoring_mode,
                location_id=data.location_id,
            )

        request = TutoringRequest(
            requester_user_id=user.id,
            learner_profile_id=learner_profile_id,
            subject_id=data.subject_id,
            location_id=data.location_id,
            tutoring_mode=data.tutoring_mode,
            description=data.description,
            preferred_schedule=data.preferred_schedule,
            selected_tutor_id=(selected_tutor.id if selected_tutor else None),
            status=TutoringRequestStatus.OPEN,
        )

        try:
            await self.requests.create(request)

            await self._notify_matching_tutors(
                request,
                selected_tutor_profile_id=(
                    selected_tutor.id if selected_tutor else None
                ),
            )

            admin_users = list((await self.db.scalars(
                select(User).where(
                    User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]),
                    User.status == UserStatus.ACTIVE,
                )
            )).all())
            notifications = NotificationService(self.db)
            for admin_user in admin_users:
                await notifications.create(
                    user_id=admin_user.id,
                    notification_type=NotificationType.ADMIN_NEW_TUTORING_REQUEST,
                    title="New tutoring request submitted",
                    message="A learner has submitted a tutoring request. Review its payment and assignment progress.",
                    data={"tutoring_request_id": str(request.id)},
                )

            await self.requests.commit()
            await self.db.refresh(request)

            return request

        except Exception:
            await self.requests.rollback()
            raise

    async def list_admin_requests(self) -> list[TutoringRequest]:
        return list((await self.db.scalars(
            select(TutoringRequest)
            .options(selectinload(TutoringRequest.requester), selectinload(TutoringRequest.subject), selectinload(TutoringRequest.location))
            .order_by(TutoringRequest.created_at.desc())
        )).all())

    async def list_my_requests(
        self,
        user: User,
    ) -> list[TutoringRequestResponse]:
        self._ensure_active_account(user)

        if role_value(user) not in {"PARENT", "ADULT_LEARNER"}:
            raise HTTPException(
                status_code=403,
                detail=("Only parents and adult learners can view their requests."),
            )

        requests = await self.requests.list_for_requester(user.id)
        response_rows: list[TutoringRequestResponse] = []

        for request in requests:
            response = TutoringRequestResponse.model_validate(request)
            if request.selected_tutor_id is not None:
                tutor_response = await self.requests.get_tutor_response(
                    request_id=request.id,
                    tutor_profile_id=request.selected_tutor_id,
                )
                response.selected_tutor_response = (
                    tutor_response.decision.value if tutor_response else None
                )
            response_rows.append(response)

        return response_rows

    async def get_my_request(
        self,
        user: User,
        request_id: uuid.UUID,
    ) -> TutoringRequest:
        self._ensure_active_account(user)

        request = await self.requests.get_by_id(request_id)

        if request is None:
            raise HTTPException(
                status_code=404,
                detail="Tutoring request not found.",
            )

        if request.requester_user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You cannot access this tutoring request.",
            )

        return request

    async def cancel(
        self,
        user: User,
        request_id: uuid.UUID,
    ) -> TutoringRequest:
        self._ensure_active_account(user)

        request = await self.requests.get_by_id_for_update(request_id)

        if request is None:
            raise HTTPException(
                status_code=404,
                detail="Tutoring request not found.",
            )

        if request.requester_user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You cannot cancel this tutoring request.",
            )

        if request.status != TutoringRequestStatus.OPEN:
            raise HTTPException(
                status_code=409,
                detail="Only open requests can be cancelled.",
            )

        request.status = TutoringRequestStatus.CANCELLED

        try:
            await self.requests.commit()
            await self.db.refresh(request)
            return request

        except Exception:
            await self.requests.rollback()
            raise

    async def list_matching_requests(
        self,
        user: User,
        limit: int = 50,
    ) -> list[TutorMatchingRequestResponse]:
        tutor = await self._get_verified_tutor(user)

        requests = await self.requests.list_for_tutor(
            tutor_profile_id=tutor.id,
            limit=limit,
        )

        subject_ids = {subject.id for subject in tutor.subjects}

        supported_modes = {
            str(getattr(mode, "value", mode)).upper()
            for mode in (tutor.tutoring_modes or [])
        }

        matched: list[TutorMatchingRequestResponse] = []

        for request in requests:
            request_status = str(
                getattr(request.status, "value", request.status)
            ).upper()

            is_accepted_assignment = (
                request_status == "ACCEPTED" and request.assigned_tutor_id == tutor.id
            )
            is_direct_request = (
                request_status == "OPEN" and request.selected_tutor_id == tutor.id
            )

            # Generic open requests must continue to match the tutor's profile.
            # A direct request is already addressed to this tutor, so it remains
            # visible even if the tutor later edits their profile.
            if not is_accepted_assignment and not is_direct_request:
                if request.subject_id not in subject_ids:
                    continue

                mode = str(
                    getattr(request.tutoring_mode, "value", request.tutoring_mode)
                ).upper()

                if mode not in supported_modes:
                    continue

                if mode in {TutoringMode.IN_PERSON.value, TutoringMode.HYBRID.value}:
                    if not await self._tutor_serves_location(
                        tutor,
                        request.location_id,
                    ):
                        continue
            else:
                mode = str(
                    getattr(request.tutoring_mode, "value", request.tutoring_mode)
                ).upper()

            requester = request.requester

            account_type = (
                getattr(
                    requester.account_type,
                    "value",
                    requester.account_type,
                )
                if requester.account_type is not None
                else None
            )

            my_response = await self.requests.get_tutor_response(
                request_id=request.id,
                tutor_profile_id=tutor.id,
            )
            matched.append(
                TutorMatchingRequestResponse(
                    id=request.id,
                    status=request.status,
                    selected_tutor_id=request.selected_tutor_id,
                    assigned_tutor_id=request.assigned_tutor_id,
                    requester_first_name=requester.first_name,
                    requester_last_name=requester.last_name,
                    requester_account_type=(
                        str(account_type) if account_type is not None else None
                    ),
                    subject_id=request.subject_id,
                    subject_name=(
                        request.subject.name
                        if request.subject
                        else "Subject unavailable"
                    ),
                    location_id=request.location_id,
                    location_name=(request.location.name if request.location else None),
                    tutoring_mode=request.tutoring_mode,
                    description=request.description,
                    preferred_schedule=request.preferred_schedule,
                    created_at=request.created_at,
                    my_response=(my_response.decision.value if my_response else None),
                )
            )

        return matched

    async def respond(
        self,
        user: User,
        request_id: uuid.UUID,
        decision: str,
    ) -> TutorRequestDecisionResult:
        tutor = await self._get_verified_tutor(user)

        request = await self.requests.get_by_id_for_update(request_id)

        if request is None:
            raise HTTPException(
                status_code=404,
                detail="Tutoring request not found.",
            )

        if request.status != TutoringRequestStatus.OPEN:
            raise HTTPException(
                status_code=409,
                detail="This request is no longer open.",
            )

        if request.requester_user_id == user.id:
            raise HTTPException(
                status_code=409,
                detail="You cannot respond to your own tutoring request.",
            )

        if (
            request.selected_tutor_id is not None
            and request.selected_tutor_id != tutor.id
        ):
            raise HTTPException(
                status_code=403,
                detail="This tutoring request was directed to another tutor.",
            )

        if decision not in {"ACCEPT", "DECLINE"}:
            raise HTTPException(
                status_code=422,
                detail="Invalid decision. Choose ACCEPT or DECLINE.",
            )

        is_direct_request_for_tutor = request.selected_tutor_id == tutor.id
        if not is_direct_request_for_tutor or decision == "ACCEPT":
            if request.subject_id not in {subject.id for subject in tutor.subjects}:
                raise HTTPException(
                    status_code=403,
                    detail="You are not registered to teach this subject.",
                )

            mode = request.tutoring_mode.value
            supported_modes = {
                str(getattr(value, "value", value)).upper()
                for value in (tutor.tutoring_modes or [])
            }

            if mode not in supported_modes:
                raise HTTPException(
                    status_code=403,
                    detail="Your profile does not support this tutoring mode.",
                )

            if mode in {TutoringMode.IN_PERSON.value, TutoringMode.HYBRID.value}:
                if not await self._tutor_serves_location(
                    tutor,
                    request.location_id,
                ):
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            "This request is outside your registered service locations."
                        ),
                    )

        existing_response = await self.requests.get_tutor_response(
            request_id=request.id,
            tutor_profile_id=tutor.id,
        )

        if existing_response is not None:
            raise HTTPException(
                status_code=409,
                detail="You have already responded to this request.",
            )

        response_decision = (
            TutorResponseDecision.ACCEPTED
            if decision == "ACCEPT"
            else TutorResponseDecision.DECLINED
        )

        response = TutorRequestResponseModel(
            tutoring_request_id=request.id,
            tutor_profile_id=tutor.id,
            decision=response_decision,
        )

        try:
            await self.requests.create_tutor_response(response)

            if response_decision == TutorResponseDecision.ACCEPTED:
                notifications = NotificationService(self.db)
                if request.selected_tutor_id is not None:
                    # Direct tutor requests have one intended tutor; their acceptance
                    # moves the request to the booking stage.
                    request.status = TutoringRequestStatus.ACCEPTED
                    request.assigned_tutor_id = tutor.id
                    request.accepted_at = datetime.now(timezone.utc)
                    message = "Your selected tutor accepted the request. You can now arrange the lesson."
                else:
                    # Generic requests collect tutor interest first. The learner
                    # explicitly chooses one responder before a booking is enabled.
                    message = "A tutor is interested in your request. Review the interested tutors and choose one to continue."

                await notifications.create(
                    user_id=request.requester_user_id,
                    notification_type=NotificationType.TUTOR_ACCEPTED_REQUEST,
                    title="A tutor responded to your request",
                    message=message,
                    data={
                        "tutoring_request_id": str(request.id),
                        "tutor_profile_id": str(tutor.id),
                    },
                )
            elif request.selected_tutor_id is not None:
                await NotificationService(self.db).create(
                    user_id=request.requester_user_id,
                    notification_type=NotificationType.TUTOR_DECLINED_REQUEST,
                    title="Your selected tutor declined the request",
                    message=(
                        "Your selected tutor is unavailable for this request. "
                        "Cancel it and submit a new request to choose another tutor."
                    ),
                    data={
                        "tutoring_request_id": str(request.id),
                        "tutor_profile_id": str(tutor.id),
                    },
                )

            await self.requests.commit()

            if decision == "ACCEPT":
                message = ("You have accepted this direct tutoring request." if request.selected_tutor_id is not None else "You have expressed interest. The learner will review your response.")
            elif request.selected_tutor_id is not None:
                message = (
                    "You have declined this request. It remains directed "
                    "to you; the learner may choose another tutor."
                )
            else:
                message = (
                    "You have declined this request. "
                    "It remains available to other eligible tutors."
                )

            return TutorRequestDecisionResult(
                request_id=request.id,
                decision=response_decision,
                request_status=request.status,
                message=message,
            )

        except Exception:
            await self.requests.rollback()
            raise

    async def select_tutor(
        self,
        user: User,
        request_id: uuid.UUID,
        tutor_profile_id: uuid.UUID,
    ) -> TutoringRequest:
        self._ensure_active_account(user)
        request = await self.requests.get_by_id_for_update(request_id)
        if request is None:
            raise HTTPException(status_code=404, detail="Tutoring request not found.")
        if request.requester_user_id != user.id:
            raise HTTPException(status_code=403, detail="You cannot select a tutor for this request.")
        if request.status != TutoringRequestStatus.OPEN or request.selected_tutor_id is not None:
            raise HTTPException(status_code=409, detail="This request is no longer accepting tutor selections.")
        response = await self.db.scalar(select(TutorRequestResponseModel).where(
            TutorRequestResponseModel.tutoring_request_id == request.id,
            TutorRequestResponseModel.tutor_profile_id == tutor_profile_id,
            TutorRequestResponseModel.decision == TutorResponseDecision.ACCEPTED,
        ))
        if response is None:
            raise HTTPException(status_code=422, detail="The selected tutor has not accepted this request.")
        tutor = await self.db.get(TutorProfile, tutor_profile_id)
        if tutor is None:
            raise HTTPException(status_code=404, detail="Selected tutor profile not found.")
        request.selected_tutor_id = tutor.id
        request.assigned_tutor_id = tutor.id
        request.status = TutoringRequestStatus.ACCEPTED
        request.accepted_at = datetime.now(timezone.utc)
        notifications = NotificationService(self.db)
        await notifications.create(
            user_id=tutor.user_id,
            notification_type=NotificationType.TUTOR_ACCEPTED_REQUEST,
            title="You have been selected for the tutoring request",
            message="The learner selected you. You can now proceed with the booking arrangement.",
            data={"tutoring_request_id": str(request.id), "tutor_profile_id": str(tutor.id)},
        )
        other_responses = list((await self.db.scalars(select(TutorRequestResponseModel).where(
            TutorRequestResponseModel.tutoring_request_id == request.id,
            TutorRequestResponseModel.decision == TutorResponseDecision.ACCEPTED,
            TutorRequestResponseModel.tutor_profile_id != tutor.id,
        ))).all())
        for other in other_responses:
            other_tutor = await self.db.get(TutorProfile, other.tutor_profile_id)
            if other_tutor:
                await notifications.create(
                    user_id=other_tutor.user_id,
                    notification_type=NotificationType.NEW_MATCHING_REQUEST,
                    title="Tutoring opportunity has been taken",
                    message="The learner selected another tutor for this request. Thank you for your interest.",
                    data={"tutoring_request_id": str(request.id), "selected_tutor_profile_id": str(tutor.id)},
                )
        await self.requests.commit()
        await self.db.refresh(request)
        return request

    async def _notify_matching_tutors(
        self,
        request: TutoringRequest,
        selected_tutor_profile_id: uuid.UUID | None = None,
    ) -> None:
        query = (
            select(TutorProfile)
            .join(User, TutorProfile.user_id == User.id)
            .options(
                selectinload(TutorProfile.subjects),
                selectinload(TutorProfile.locations),
            )
            .where(
                User.role == UserRole.TUTOR,
                User.status == UserStatus.ACTIVE,
            )
        )

        if selected_tutor_profile_id is not None:
            query = query.where(TutorProfile.id == selected_tutor_profile_id)

        result = await self.db.execute(query)
        tutors = result.scalars().unique().all()

        verification_result = await self.db.execute(
            select(TutorVerification.tutor_user_id).where(
                TutorVerification.status == VerificationStatus.APPROVED
            )
        )
        verified_user_ids = set(verification_result.scalars().all())

        notifications = NotificationService(self.db)

        for tutor in tutors:
            if tutor.user_id not in verified_user_ids:
                continue

            if request.subject_id not in {subject.id for subject in tutor.subjects}:
                continue

            supported_modes = {
                str(getattr(mode, "value", mode)).upper()
                for mode in (tutor.tutoring_modes or [])
            }

            mode = request.tutoring_mode.value

            if mode not in supported_modes:
                continue

            if mode in {TutoringMode.IN_PERSON.value, TutoringMode.HYBRID.value}:
                if not await self._tutor_serves_location(
                    tutor,
                    request.location_id,
                ):
                    continue

            await notifications.create(
                user_id=tutor.user_id,
                notification_type=NotificationType.NEW_MATCHING_REQUEST,
                title=(
                    "You have been selected for a tutoring request"
                    if selected_tutor_profile_id is not None
                    else "New tutoring request"
                ),
                message=(
                    "A learner has selected you for a tutoring request. "
                    "Review the request and accept or decline it."
                    if selected_tutor_profile_id is not None
                    else (
                        "A new tutoring request matches your subjects "
                        "and teaching preferences."
                    )
                ),
                data={
                    "tutoring_request_id": str(request.id),
                },
            )

    async def list_matching_tutors(
        self,
        user: User,
        request_id: uuid.UUID,
    ) -> list[MatchingTutorResponse]:
        self._ensure_active_account(user)

        if role_value(user) not in {"PARENT", "ADULT_LEARNER"}:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Only parents and adult learners can discover matching tutors."
                ),
            )

        request = await self.get_my_request(
            user=user,
            request_id=request_id,
        )

        if request.status != TutoringRequestStatus.OPEN:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Matching tutors are only available for open tutoring requests."
                ),
            )

        subject_result = await self.db.execute(
            select(Subject).where(Subject.id == request.subject_id)
        )
        requested_subject = subject_result.scalar_one_or_none()

        subject_name = (
            requested_subject.name if requested_subject else "the requested subject"
        )

        requested_location = None

        if (
            request.tutoring_mode in {TutoringMode.IN_PERSON, TutoringMode.HYBRID}
            and request.location_id is not None
        ):
            location_result = await self.db.execute(
                select(Location).where(Location.id == request.location_id)
            )
            requested_location = location_result.scalar_one_or_none()

        requested_location_name = (
            requested_location.name if requested_location else None
        )

        candidates = await self.requests.list_discoverable_tutors()

        matches: list[MatchingTutorResponse] = []
        requested_mode = request.tutoring_mode.value

        for tutor, tutor_user in candidates:
            if (
                request.selected_tutor_id is not None
                and tutor.id != request.selected_tutor_id
            ):
                continue

            tutor_subject_ids = {subject.id for subject in tutor.subjects}

            supported_modes = {
                str(getattr(mode, "value", mode)).upper()
                for mode in (tutor.tutoring_modes or [])
            }

            if request.subject_id not in tutor_subject_ids:
                continue

            if requested_mode not in supported_modes:
                continue

            location_matches = True

            if requested_mode in {TutoringMode.IN_PERSON.value, TutoringMode.HYBRID.value}:
                location_matches = await self._tutor_serves_location(
                    tutor,
                    request.location_id,
                )

            match_level = "STRONG" if location_matches else "PARTIAL"

            match_reasons = [
                f"Teaches {subject_name}.",
                (
                    "Supports online tutoring."
                    if requested_mode == TutoringMode.ONLINE.value
                    else (
                        "Supports hybrid tutoring."
                        if requested_mode == TutoringMode.HYBRID.value
                        else "Supports in-person tutoring."
                    )
                ),
            ]

            unmatched_criteria = []

            if requested_mode in {TutoringMode.IN_PERSON.value, TutoringMode.HYBRID.value}:
                if location_matches:
                    match_reasons.append(
                        "Serves the requested location or a broader area containing it."
                    )
                else:
                    unmatched_criteria.append("LOCATION")
                    match_reasons.append(
                        "This tutor does not currently list the requested "
                        "location or a parent service area."
                    )

            tutor_subject_names = sorted(subject.name for subject in tutor.subjects)
            tutor_location_names = sorted(location.name for location in tutor.locations)

            matches.append(
                MatchingTutorResponse(
                    tutor_user_id=tutor_user.id,
                    first_name=tutor_user.first_name,
                    last_name=tutor_user.last_name,
                    bio=tutor.bio,
                    monthly_fee=tutor.monthly_fee,
                    qualifications=tutor.qualifications,
                    years_of_experience=tutor.years_of_experience,
                    teaching_languages=tutor.teaching_languages or [],
                    learner_age_groups=tutor.learner_age_groups or [],
                    tutoring_modes=tutor.tutoring_modes or [],
                    service_area=tutor.service_area,
                    subjects=tutor_subject_names,
                    locations=tutor_location_names,
                    match_level=match_level,
                    match_reasons=match_reasons,
                    unmatched_criteria=unmatched_criteria,
                )
            )

        response_rows = list((await self.db.scalars(
            select(TutorRequestResponseModel).where(
                TutorRequestResponseModel.tutoring_request_id == request.id
            )
        )).all())
        response_by_tutor = {row.tutor_profile_id: row.decision.value for row in response_rows}
        profile_ids_by_user = {tutor.user_id: tutor.id for tutor, _ in candidates}
        for item in matches:
            item.tutor_profile_id = profile_ids_by_user.get(item.tutor_user_id)
            item.response_decision = response_by_tutor.get(item.tutor_profile_id)

        matches.sort(
            key=lambda item: (
                item.match_level != "STRONG",
                -item.years_of_experience,
                item.first_name.lower(),
            )
        )

        return matches
