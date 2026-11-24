import uuid

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DBSession, RequireBookingAdmin
from app.domain.progress_logs.models.progress_log_entry import ProgressLogReviewStatus
from app.domain.progress_logs.schemas.progress_log import (
    ProgressLogCreate,
    ProgressLogResponse,
    ProgressLogReview,
    ProgressLogRoomResponse,
)
from app.domain.progress_logs.services.progress_log_service import ProgressLogService

router = APIRouter(prefix="/progress-logs", tags=["Daily Progress Logs"])




@router.get("/rooms", response_model=list[ProgressLogRoomResponse])
async def list_progress_log_rooms(
    current_user: CurrentUser,
    db: DBSession,
):
    return await ProgressLogService(db).list_rooms(current_user)

@router.post("/requests/{request_id}", response_model=ProgressLogResponse, status_code=201)
async def create_progress_log_entry(
    request_id: uuid.UUID,
    payload: ProgressLogCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    return await ProgressLogService(db).create(current_user, request_id, payload)


@router.get("/requests/{request_id}", response_model=list[ProgressLogResponse])
async def list_progress_log_entries(
    request_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    return await ProgressLogService(db).list_for_request(current_user, request_id)


@router.get("/admin", response_model=list[ProgressLogResponse])
async def list_admin_progress_log_entries(
    _: RequireBookingAdmin,
    db: DBSession,
    review_status: ProgressLogReviewStatus | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
):
    return await ProgressLogService(db).list_admin(review_status, limit)


@router.patch("/admin/{entry_id}/review", response_model=ProgressLogResponse)
async def review_progress_log_entry(
    entry_id: uuid.UUID,
    payload: ProgressLogReview,
    admin: RequireBookingAdmin,
    db: DBSession,
):
    return await ProgressLogService(db).review(admin, entry_id, payload)
