from fastapi import APIRouter
from app.domain.agreements.routers.agreement_router import router as agreement_router

from app.domain.authentication.routers.auth_router import router as auth_router
from app.domain.learners.routers.learner_router import router as learner_router
from app.domain.locations.routers.location_router import router as location_router
from app.domain.notifications.routers.notification_router import (
    router as notification_router,
)
from app.domain.parents.routers.parent_router import router as parent_router
from app.domain.progress_reports.routers.progress_report_router import router as progress_report_router
from app.domain.progress_logs.routers.progress_log_router import router as progress_log_router
from app.domain.payments.routers.payment_router import router as payment_router
from app.domain.session_bookings.routers.booking_router import (
    router as session_booking_router,
)
from app.domain.subjects.routers.subject_router import router as subject_router
from app.domain.tutoring_requests.routers.tutoring_request_router import (
    router as tutoring_request_router,
)
from app.domain.tutors.routers.admin_tutor_router import (
    router as admin_tutor_router,
)
from app.domain.tutors.routers.tutor_router import router as tutor_router
from app.domain.tutor_background.routers.background_router import router as tutor_background_router
from app.domain.verification.routers.verification_router import (
    router as verification_router,
)

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(agreement_router)
api_router.include_router(admin_tutor_router)
api_router.include_router(parent_router)
api_router.include_router(progress_report_router)
api_router.include_router(progress_log_router)
api_router.include_router(payment_router)
api_router.include_router(session_booking_router)
api_router.include_router(notification_router)
api_router.include_router(verification_router)
api_router.include_router(tutoring_request_router)
api_router.include_router(tutor_router)
api_router.include_router(tutor_background_router)
api_router.include_router(learner_router)
api_router.include_router(location_router)
api_router.include_router(subject_router)


@api_router.get("/health", tags=["System"])
async def health_check():
    return {
        "success": True,
        "message": "Tutova API is running",
    }
