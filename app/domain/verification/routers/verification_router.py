import uuid
from typing import Annotated

from fastapi import APIRouter, File, Query, Request, UploadFile, status

from app.core.dependencies import (
    DBSession,
    RequireBookingAdmin,
    RequireTutor,
)
from app.domain.tutors.schemas.tutor import (
    IdentityDocumentDownloadResponse,
    IdentityDocumentUploadResponse,
)
from app.domain.verification.schemas.verification import (
    AdminVerificationResponse,
    VerificationReviewRequest,
    VerificationStatusResponse,
    VerificationSubmission,
)
from app.domain.verification.schemas.referee import (
    RefereeConsentPageResponse,
    RefereeConsentSubmission,
    AdminTutorRefereeResponse,
    TutorRefereeInviteRequest,
    TutorRefereeResponse,
    SafeguardingReviewRequest,
)
from app.domain.verification.services.referee_service import RefereeService
from app.domain.verification.services.identity_document_service import (
    IdentityDocumentService,
    settings,
)
from app.domain.verification.services.verification_service import (
    VerificationService,
)

router = APIRouter(
    prefix="/verification",
    tags=["Tutor Verification"],
)


@router.post(
    "/tutor/referees",
    response_model=list[TutorRefereeResponse],
    status_code=status.HTTP_200_OK,
)
async def invite_tutor_referees(
    payload: TutorRefereeInviteRequest,
    current_user: RequireTutor,
    db: DBSession,
):
    return await RefereeService(db).invite(current_user, payload)


@router.get("/tutor/referees", response_model=list[TutorRefereeResponse])
async def list_tutor_referees(current_user: RequireTutor, db: DBSession):
    return await RefereeService(db).list_mine(current_user)


@router.get(
    "/admin/{verification_id}/referees",
    response_model=list[AdminTutorRefereeResponse],
)
async def list_verification_referees(
    verification_id: uuid.UUID, current_user: RequireBookingAdmin, db: DBSession
):
    return await RefereeService(db).list_for_verification_admin(
        current_user, verification_id
    )


@router.get("/referee/{token}", response_model=RefereeConsentPageResponse)
async def get_referee_consent_form(token: str, db: DBSession):
    return await RefereeService(db).get_consent_page(token)


@router.post("/referee/{token}/consent", response_model=RefereeConsentPageResponse)
async def submit_referee_consent(
    token: str,
    payload: RefereeConsentSubmission,
    request: Request,
    db: DBSession,
):
    client_ip = request.client.host if request.client else None
    return await RefereeService(db).submit_consent(
        token, payload, client_ip=client_ip
    )


@router.post(
    "/admin/{verification_id}/safeguarding-review",
    response_model=AdminVerificationResponse,
)
async def review_safeguarding_flag(
    verification_id: uuid.UUID,
    data: SafeguardingReviewRequest,
    current_user: RequireBookingAdmin,
    db: DBSession,
):
    result = await VerificationService(db).review_safeguarding_flag(
        current_user, verification_id, data
    )
    await db.commit()
    return result


@router.post(
    "/tutor/submit",
    response_model=VerificationStatusResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_verification(
    data: VerificationSubmission,
    current_user: RequireTutor,
    db: DBSession,
):
    result = await VerificationService(db).submit(current_user, data)
    await db.commit()
    return result


@router.get(
    "/tutor/me",
    response_model=VerificationStatusResponse,
)
async def get_my_verification(
    current_user: RequireTutor,
    db: DBSession,
):
    return await VerificationService(db).get_my_status(current_user)


@router.get(
    "/admin/pending",
    response_model=list[AdminVerificationResponse],
)
async def list_pending_verifications(
    current_user: RequireBookingAdmin,
    db: DBSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await VerificationService(db).list_pending(
        current_user,
        limit,
    )


@router.post(
    "/admin/{verification_id}/review",
    response_model=AdminVerificationResponse,
)
async def review_verification(
    verification_id: uuid.UUID,
    data: VerificationReviewRequest,
    current_user: RequireBookingAdmin,
    db: DBSession,
):
    result = await VerificationService(db).review(
        current_user,
        verification_id,
        data,
    )
    await db.commit()
    return result


@router.post(
    "/tutor/identity-document",
    response_model=IdentityDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_identity_document(
    db: DBSession,
    user: RequireTutor,
    file: UploadFile = File(...),
):
    service = IdentityDocumentService(db)

    result = await service.upload(user, file)

    await db.commit()

    # Delete the previous asset only after the new key is committed.
    service.delete_old_document(result["old_key"])

    return IdentityDocumentUploadResponse(
        message=result["message"],
        identity_document_type=file.content_type,
    )


@router.get(
    "/admin/{verification_id}/identity-document",
    response_model=IdentityDocumentDownloadResponse,
)
async def get_identity_document_download(
    verification_id: uuid.UUID,
    db: DBSession,
    admin: RequireBookingAdmin,
):
    service = IdentityDocumentService(db)

    download_url = await service.get_admin_download_url(
        admin,
        verification_id,
    )

    return IdentityDocumentDownloadResponse(
        download_url=download_url,
        expires_in_seconds=settings.CLOUDINARY_IDENTITY_DOCUMENT_URL_TTL_SECONDS,
    )
