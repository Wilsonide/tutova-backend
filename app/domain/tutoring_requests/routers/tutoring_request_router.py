import uuid

from fastapi import APIRouter, BackgroundTasks, Query, status

from app.core.dependencies import (
    DBSession,
    RequireRequester,
    RequireTutor,
    RequireBookingAdmin,
)
from app.domain.tutoring_requests.schemas.matching_tutor import MatchingTutorResponse
from app.domain.tutoring_requests.schemas.tutoring_request import (
    TutoringRequestCreate,
    TutoringRequestResponse,
    TutorMatchingRequestResponse,
    TutorRequestDecision,
    TutorRequestDecisionResult,
)
from app.domain.tutoring_requests.services.tutoring_request_service import (
    TutoringRequestService,
)

router = APIRouter(
    prefix="/tutoring-requests",
    tags=["Tutoring Requests"],
)


# =====================================================
# CREATE TUTORING REQUEST - PARENT / ADULT LEARNER
# =====================================================


@router.post(
    "",
    response_model=TutoringRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tutoring_request(
    payload: TutoringRequestCreate,
    current_user: RequireRequester,
    db: DBSession,
):
    service = TutoringRequestService(db)

    return await service.create(
        current_user,
        payload,
    )


# =====================================================
# LIST MY REQUESTS - PARENT / ADULT LEARNER
# =====================================================


@router.get(
    "/mine",
    response_model=list[TutoringRequestResponse],
)
async def list_my_tutoring_requests(
    current_user: RequireRequester,
    db: DBSession,
):
    service = TutoringRequestService(db)

    return await service.list_my_requests(current_user)


# =====================================================
# GET MY REQUEST - PARENT / ADULT LEARNER
# =====================================================


@router.get(
    "/mine/{request_id}",
    response_model=TutoringRequestResponse,
)
async def get_my_tutoring_request(
    request_id: uuid.UUID,
    current_user: RequireRequester,
    db: DBSession,
):
    service = TutoringRequestService(db)

    return await service.get_my_request(
        current_user,
        request_id,
    )


# =====================================================
# CANCEL MY REQUEST - PARENT / ADULT LEARNER
# =====================================================


@router.post(
    "/mine/{request_id}/cancel",
    response_model=TutoringRequestResponse,
)
async def cancel_tutoring_request(
    request_id: uuid.UUID,
    current_user: RequireRequester,
    db: DBSession,
):
    service = TutoringRequestService(db)

    return await service.cancel(
        current_user,
        request_id,
    )


# =====================================================
# LIST MATCHING REQUESTS - TUTOR ONLY
# =====================================================


@router.get(
    "/matching",
    response_model=list[TutorMatchingRequestResponse],
)
async def list_matching_tutoring_requests(
    current_user: RequireTutor,
    db: DBSession,
    limit: int = Query(default=50, ge=1, le=100),
):
    service = TutoringRequestService(db)

    return await service.list_matching_requests(
        current_user,
        limit=limit,
    )


# =====================================================
# RESPOND TO REQUEST - TUTOR ONLY
# =====================================================


@router.post(
    "/{request_id}/respond",
    response_model=TutorRequestDecisionResult,
)
async def respond_to_tutoring_request(
    request_id: uuid.UUID,
    payload: TutorRequestDecision,
    current_user: RequireTutor,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    service = TutoringRequestService(db)

    return await service.respond(
        current_user,
        request_id,
        payload.decision,
        background_tasks,
    )


@router.get(
    "/mine/{request_id}/matching-tutors",
    response_model=list[MatchingTutorResponse],
)
async def get_matching_tutors(
    request_id: uuid.UUID,
    current_user: RequireRequester,
    db: DBSession,
):
    return await TutoringRequestService(db).list_matching_tutors(
        user=current_user,
        request_id=request_id,
    )


@router.post(
    "/mine/{request_id}/select-tutor/{tutor_profile_id}",
    response_model=TutoringRequestResponse,
)
async def select_tutor_for_request(
    request_id: uuid.UUID,
    tutor_profile_id: uuid.UUID,
    current_user: RequireRequester,
    db: DBSession,
):
    return await TutoringRequestService(db).select_tutor(
        current_user, request_id, tutor_profile_id
    )


@router.get("/admin", response_model=list[TutoringRequestResponse])
async def list_all_tutoring_requests(_: RequireBookingAdmin, db: DBSession):
    return await TutoringRequestService(db).list_admin_requests()
