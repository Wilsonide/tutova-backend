import logging
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.cloudinary_service import (
    ALLOWED_VIDEO_CONTENT_TYPES,
    MAX_INTRO_VIDEO_SIZE,
    create_tutor_video_upload_signature,
    get_tutor_video_url,
    tutor_video_public_id,
    upload_tutor_video,
    # Keep your other imports.
    verify_tutor_video_upload,
)
from app.domain.authentication.models.user import User, UserRole
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.tutors.repositories.tutor_repository import TutorRepository
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class TutorVideoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tutors = TutorRepository(db)

    @staticmethod
    def _require_tutor(user: User):
        if user.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tutors can manage introduction videos.",
            )

    async def create_upload_signature(self, user: User) -> dict:
        if user.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tutors can upload introduction videos.",
            )

        tutor_profile = await self.db.scalar(
            select(TutorProfile).where(TutorProfile.user_id == user.id)
        )

        if not tutor_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Create your tutor profile before uploading an introduction video."
                ),
            )

        try:
            return await run_in_threadpool(
                create_tutor_video_upload_signature,
                str(user.id),
            )

        except Exception as exc:
            logger.exception(
                "Failed to create tutor video upload signature. Tutor user ID: %s",
                user.id,
            )

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not prepare the video upload.",
            ) from exc

    async def complete_upload(
        self,
        user: User,
        uploaded_public_id: str,
    ) -> str:
        self._require_tutor(user)

        tutor_profile = await self.db.scalar(
            select(TutorProfile).where(TutorProfile.user_id == user.id)
        )

        if not tutor_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Create your tutor profile before uploading an introduction video."
                ),
            )

        try:
            public_id = await run_in_threadpool(
                verify_tutor_video_upload,
                uploaded_public_id,
                str(user.id),
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not verify the uploaded introduction video.",
            ) from exc

        verification = await self.db.scalar(
            select(TutorVerification)
            .where(TutorVerification.tutor_user_id == user.id)
            .with_for_update()
        )

        if verification is None:
            verification = TutorVerification(
                tutor_user_id=user.id,
                status=VerificationStatus.NOT_SUBMITTED,
            )
            self.db.add(verification)

        verification.introduction_video_key = public_id

        await self.db.flush()

        return get_tutor_video_url(public_id)

    async def upload(self, user: User, file: UploadFile) -> str:
        self._require_tutor(user)

        profile = await self.tutors.get_by_user_id(user.id)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Create your tutor profile before uploading an introduction video.",
            )

        if file.content_type not in ALLOWED_VIDEO_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only MP4 and WebM videos are supported.",
            )

        content = await file.read(MAX_INTRO_VIDEO_SIZE + 1)

        if not content:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The uploaded video is empty.",
            )

        if len(content) > MAX_INTRO_VIDEO_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="The introduction video must not exceed 100 MB.",
            )

        await file.seek(0)

        # Upload to Cloudinary before changing the database record.
        uploaded = upload_tutor_video(file.file, str(user.id))
        public_id = uploaded.get("public_id")

        expected_public_id = tutor_video_public_id(str(user.id))

        if public_id != expected_public_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The video provider returned an unexpected asset identifier.",
            )

        result = await self.db.execute(
            select(TutorVerification)
            .where(TutorVerification.tutor_user_id == user.id)
            .with_for_update()
        )
        verification = result.scalar_one_or_none()

        if verification is None:
            verification = TutorVerification(
                tutor_user_id=user.id,
                status=VerificationStatus.NOT_SUBMITTED,
                introduction_video_key=public_id,
            )
            self.db.add(verification)
        else:
            verification.introduction_video_key = public_id

        await self.db.flush()

        return get_tutor_video_url(public_id)

    async def delete(self, user: User) -> str:
        self._require_tutor(user)

        result = await self.db.execute(
            select(TutorVerification)
            .where(TutorVerification.tutor_user_id == user.id)
            .with_for_update()
        )

        verification = result.scalar_one_or_none()

        if not verification or not verification.introduction_video_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No introduction video was found.",
            )

        public_id = verification.introduction_video_key

        # Clear the database reference first. The router commits this change.
        verification.introduction_video_key = None
        await self.db.flush()

        # Cloudinary deletion is performed after the database commit
        # by the router, to avoid deleting an asset before its DB update.
        return public_id
