import uuid
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    File,
    Query,
    UploadFile,
    status,
)

from app.core.cloudinary_service import delete_tutor_video
from app.core.dependencies import DBSession, RequireTutor
from app.domain.tutors.schemas.public_tutor import (
    PublicTutorListResponse,
    PublicTutorResponse,
    TutorVideoUploadResponse,
)
from app.domain.tutors.schemas.tutor import (
    TutorMediaDeleteResponse,
    TutorProfileCreate,
    TutorProfilePictureResponse,
    TutorProfileResponse,
    TutorProfileUpdate,
    TutorVideoUploadCompleteRequest,
    TutorVideoUploadSignatureResponse,
)
from app.domain.tutors.schemas.tutor_catalog import TutorCatalogSelection
from app.domain.tutors.services.public_tutor_service import PublicTutorService
from app.domain.tutors.services.tutor_picture_service import (
    TutorPictureService,
)
from app.domain.tutors.services.tutor_service import TutorService
from app.domain.tutors.services.tutor_video_service import TutorVideoService

router = APIRouter(
    prefix="/tutors",
    tags=["Tutors"],
)

# =====================================================
# PUBLIC TUTOR DISCOVERY
# =====================================================


@router.get(
    "",
    response_model=PublicTutorListResponse,
)
async def discover_tutors(
    db: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=50)] = 12,
    search: Annotated[str | None, Query(max_length=150)] = None,
    subject_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    tutoring_mode: Literal["ONLINE", "IN_PERSON", "HYBRID"] | None = None,
):
    return await PublicTutorService(db).list_tutors(
        page=page,
        per_page=per_page,
        search=search,
        subject_id=subject_id,
        location_id=location_id,
        tutoring_mode=tutoring_mode,
    )


# =====================================================
# CREATE TUTOR PROFILE - TUTOR ONLY
# =====================================================


@router.post(
    "/profile",
    response_model=TutorProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tutor_profile(
    data: TutorProfileCreate,
    current_user: RequireTutor,
    db: DBSession,
):
    profile = await TutorService(db).create_profile(
        current_user,
        data,
    )

    await db.commit()

    return profile


# =====================================================
# GET MY TUTOR PROFILE - TUTOR ONLY
# =====================================================


@router.get(
    "/profile",
    response_model=TutorProfileResponse,
)
async def get_tutor_profile(
    current_user: RequireTutor,
    db: DBSession,
):
    return await TutorService(db).get_profile_response(current_user)


# =====================================================
# UPDATE TUTOR PROFILE - TUTOR ONLY
# =====================================================


@router.patch(
    "/profile",
    response_model=TutorProfileResponse,
)
async def update_tutor_profile(
    data: TutorProfileUpdate,
    current_user: RequireTutor,
    db: DBSession,
):
    profile = await TutorService(db).update_profile(
        current_user,
        data,
    )

    await db.commit()

    return profile


# =====================================================
# UPDATE TUTOR SUBJECTS AND LOCATIONS - TUTOR ONLY
# =====================================================


@router.put("/profile/catalog")
async def update_tutor_catalog(
    data: TutorCatalogSelection,
    current_user: RequireTutor,
    db: DBSession,
):
    profile = await TutorService(db).update_catalog_selection(
        current_user,
        data,
    )

    await db.commit()

    return {
        "message": "Tutor subjects and locations updated.",
        "subject_ids": [subject.id for subject in profile.subjects],
        "location_ids": [location.id for location in profile.locations],
    }


# =====================================================
# UPLOAD / REPLACE INTRODUCTION VIDEO - TUTOR ONLY
# =====================================================


@router.post(
    "/profile/introduction-video",
    response_model=TutorVideoUploadResponse,
)
async def upload_introduction_video(
    current_user: RequireTutor,
    db: DBSession,
    file: Annotated[UploadFile, File(...)],
):
    video_url = await TutorVideoService(db).upload(
        current_user,
        file,
    )

    await db.commit()

    return TutorVideoUploadResponse(
        message="Introduction video uploaded successfully.",
        introduction_video_url=video_url,
    )


@router.post(
    "/profile/introduction-video/signature",
    response_model=TutorVideoUploadSignatureResponse,
)
async def create_introduction_video_upload_signature(
    current_user: RequireTutor,
    db: DBSession,
):
    authorization = await TutorVideoService(db).create_upload_signature(
        current_user,
    )

    return TutorVideoUploadSignatureResponse(**authorization)


@router.post(
    "/profile/introduction-video/complete",
    response_model=TutorVideoUploadResponse,
)
async def complete_introduction_video_upload(
    payload: TutorVideoUploadCompleteRequest,
    current_user: RequireTutor,
    db: DBSession,
):
    video_url = await TutorVideoService(db).complete_upload(
        current_user,
        payload.public_id,
    )

    await db.commit()

    return TutorVideoUploadResponse(
        message="Introduction video uploaded successfully.",
        introduction_video_url=video_url,
    )


# =====================================================
# DELETE INTRODUCTION VIDEO - TUTOR ONLY
# =====================================================


@router.delete(
    "/profile/introduction-video",
    status_code=status.HTTP_200_OK,
)
async def delete_introduction_video(
    current_user: RequireTutor,
    db: DBSession,
):
    public_id = await TutorVideoService(db).delete(current_user)

    await db.commit()

    # Delete the Cloudinary asset only after the database commit.
    delete_tutor_video(public_id)

    return {
        "message": "Introduction video deleted successfully.",
    }


# =====================================================
# PUBLIC TUTOR DETAILS
# Keep this dynamic route after /profile routes.
# =====================================================


@router.get(
    "/{tutor_id}",
    response_model=PublicTutorResponse,
)
async def get_public_tutor(
    tutor_id: uuid.UUID,
    db: DBSession,
):
    return await PublicTutorService(db).get_tutor(tutor_id)


@router.post(
    "/profile/picture",
    response_model=TutorProfilePictureResponse,
)
async def upload_profile_picture(
    file: UploadFile = File(...),
    db: DBSession = None,
    user: RequireTutor = None,
):
    service = TutorPictureService(db)
    result = await service.upload(user, file)

    await db.commit()

    # The new picture is now referenced by the committed database row.
    service.delete_old_picture(result["old_key"])

    return TutorProfilePictureResponse(
        message="Profile picture uploaded successfully.",
        profile_picture_url=result["profile_picture_url"],
    )


@router.delete(
    "/profile/picture",
    response_model=TutorMediaDeleteResponse,
)
async def delete_profile_picture(
    db: DBSession,
    user: RequireTutor,
):
    service = TutorPictureService(db)
    old_key = await service.delete(user)

    await db.commit()

    service.delete_old_picture(old_key)

    return TutorMediaDeleteResponse(message="Profile picture deleted successfully.")
