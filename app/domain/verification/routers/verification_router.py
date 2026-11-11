import uuid
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status

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
