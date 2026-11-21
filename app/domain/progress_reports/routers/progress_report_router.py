import uuid
from fastapi import APIRouter, Query
from app.core.dependencies import CurrentUser, DBSession, RequireBookingAdmin
from app.domain.progress_reports.models.progress_report import ProgressReportReviewStatus
from app.domain.progress_reports.schemas.progress_report import ProgressReportCreate, ProgressReportResponse, ProgressReportReview
from app.domain.progress_reports.services.progress_report_service import ProgressReportService

router = APIRouter(prefix="/progress-reports", tags=["Progress Reports"])

@router.post("/bookings/{booking_id}", response_model=ProgressReportResponse, status_code=201)
async def submit_progress_report(booking_id: uuid.UUID, payload: ProgressReportCreate, current_user: CurrentUser, db: DBSession):
    return await ProgressReportService(db).submit(current_user, booking_id, payload)

@router.get("/bookings/{booking_id}", response_model=list[ProgressReportResponse])
async def list_booking_reports(booking_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await ProgressReportService(db).list_for_booking(current_user, booking_id)

@router.get("/admin", response_model=list[ProgressReportResponse])
async def list_admin_reports(_: RequireBookingAdmin, db: DBSession, review_status: ProgressReportReviewStatus | None = Query(default=None)):
    return await ProgressReportService(db).list_admin(review_status)

@router.patch("/admin/{report_id}/review", response_model=ProgressReportResponse)
async def review_progress_report(report_id: uuid.UUID, payload: ProgressReportReview, admin: RequireBookingAdmin, db: DBSession):
    return await ProgressReportService(db).review(admin, report_id, payload)
