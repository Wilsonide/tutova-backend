import uuid

from fastapi import APIRouter, Query, status

from app.core.dependencies import (
    CurrentUser,
    DBSession,
    RequireBookingParticipant,
    RequireRequester,
    RequireTutor,
    RequireBookingAdmin,
)
from app.domain.session_bookings.schemas.booking import (
    BookingAccept,
    BookingCancel,
    BookingCreate,
    BookingDecline,
    BookingDispute,
    BookingResponse,
    AdminBookingReview,
)
from app.domain.session_bookings.services.booking_service import (
    BookingService,
)

router = APIRouter(
    prefix="/session-bookings",
    tags=["Session Bookings"],
)


# =====================================================
# CREATE BOOKING - PARENT / ADULT LEARNER
# =====================================================


@router.post(
    "/requests/{request_id}",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    request_id: uuid.UUID,
    payload: BookingCreate,
    current_user: RequireRequester,
    db: DBSession,
):
    service = BookingService(db)

    return await service.create_booking(
        current_user,
        request_id,
        payload,
    )


# =====================================================
# LIST MY BOOKINGS - AUTHENTICATED USERS
# =====================================================


@router.get(
    "/mine",
    response_model=list[BookingResponse],
)
async def list_my_bookings(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    service = BookingService(db)

    return await service.list_my_bookings(
        current_user,
        limit,
        offset,
    )


# =====================================================
# GET BOOKING - AUTHENTICATED USERS
# =====================================================


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
)
async def get_booking(
    booking_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = BookingService(db)

    return await service.get_booking(
        current_user,
        booking_id,
    )


# =====================================================
# ACCEPT BOOKING - TUTOR ONLY
# =====================================================


@router.post(
    "/{booking_id}/accept",
    response_model=BookingResponse,
)
async def accept_booking(
    booking_id: uuid.UUID,
    payload: BookingAccept,
    current_user: RequireTutor,
    db: DBSession,
):
    service = BookingService(db)

    return await service.accept_booking(
        current_user,
        booking_id,
        payload,
    )


# =====================================================
# DECLINE BOOKING - TUTOR ONLY
# =====================================================


@router.post(
    "/{booking_id}/decline",
    response_model=BookingResponse,
)
async def decline_booking(
    booking_id: uuid.UUID,
    payload: BookingDecline,
    current_user: RequireTutor,
    db: DBSession,
):
    service = BookingService(db)

    return await service.decline_booking(
        current_user,
        booking_id,
        payload.reason,
    )


# =====================================================
# LEGACY CONFIRM BOOKING - EXISTING BOOKINGS ONLY
# =====================================================


@router.post(
    "/{booking_id}/confirm",
    response_model=BookingResponse,
)
async def confirm_booking(
    booking_id: uuid.UUID,
    current_user: RequireRequester,
    db: DBSession,
):
    service = BookingService(db)

    return await service.confirm_booking(
        current_user,
        booking_id,
    )


# =====================================================
# CANCEL BOOKING - PARTICIPANTS
# =====================================================


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
)
async def cancel_booking(
    booking_id: uuid.UUID,
    payload: BookingCancel,
    current_user: RequireBookingParticipant,
    db: DBSession,
):
    service = BookingService(db)

    return await service.cancel_booking(
        current_user,
        booking_id,
        payload.reason,
    )


# =====================================================
# REPORT SESSION COMPLETION - TUTOR ONLY
# =====================================================


@router.post(
    "/{booking_id}/complete",
    response_model=BookingResponse,
)
async def complete_booking(
    booking_id: uuid.UUID,
    current_user: RequireTutor,
    db: DBSession,
):
    service = BookingService(db)

    return await service.complete_booking(
        current_user,
        booking_id,
    )


# =====================================================
# ACKNOWLEDGE COMPLETION - PARENT / ADULT LEARNER
# =====================================================


@router.post(
    "/{booking_id}/acknowledge-completion",
    response_model=BookingResponse,
)
async def acknowledge_completion(
    booking_id: uuid.UUID,
    current_user: RequireRequester,
    db: DBSession,
):
    service = BookingService(db)

    return await service.acknowledge_completion(
        current_user,
        booking_id,
    )


# =====================================================
# DISPUTE COMPLETION - PARENT / ADULT LEARNER
# =====================================================


@router.post(
    "/{booking_id}/dispute-completion",
    response_model=BookingResponse,
)
async def dispute_completion(
    booking_id: uuid.UUID,
    payload: BookingDispute,
    current_user: RequireRequester,
    db: DBSession,
):
    service = BookingService(db)

    return await service.dispute_completion(
        current_user,
        booking_id,
        payload.reason,
    )


@router.get("/admin", response_model=list[BookingResponse])
async def list_all_bookings(
    _: RequireBookingAdmin,
    db: DBSession,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    from sqlalchemy import select
    from app.domain.session_bookings.models.lesson_booking import LessonBooking
    return list((await db.scalars(
        select(LessonBooking).order_by(LessonBooking.start_at.desc()).limit(limit).offset(offset)
    )).all())


@router.post("/admin/{booking_id}/resolve-dispute", response_model=BookingResponse)
async def resolve_booking_dispute(
    booking_id: uuid.UUID,
    payload: AdminBookingReview,
    admin: RequireBookingAdmin,
    db: DBSession,
):
    return await BookingService(db).admin_review_dispute(
        admin, booking_id, payload.resolution, payload.notes
    )
