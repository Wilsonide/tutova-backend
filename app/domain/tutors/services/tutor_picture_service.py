from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cloudinary_service import (
    delete_tutor_profile_picture,
    get_tutor_profile_picture_url,
    upload_tutor_profile_picture,
)
from app.core.config import settings
from app.domain.authentication.models.user import User, UserRole
from app.domain.tutors.repositories.tutor_repository import TutorRepository


class TutorPictureService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tutors = TutorRepository(db)

    async def upload(self, user: User, file):
        if user.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tutor accounts can upload profile pictures.",
            )

        profile = await self.tutors.get_by_user_id_for_update(user.id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Create your tutor profile before uploading a picture.",
            )

        if file.content_type not in {
            "image/jpeg",
            "image/png",
            "image/webp",
        }:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Profile pictures must be JPEG, PNG, or WebP images.",
            )

        content = await file.read(settings.CLOUDINARY_PROFILE_PICTURE_MAX_SIZE + 1)

        if not content:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The uploaded picture is empty.",
            )

        if len(content) > settings.CLOUDINARY_PROFILE_PICTURE_MAX_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Profile pictures must not exceed 5 MB.",
            )

        uploaded = upload_tutor_profile_picture(
            content=content,
            tutor_user_id=str(user.id),
            content_type=file.content_type,
        )

        new_key = uploaded.get("public_id")
        if not new_key:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Cloudinary did not return a profile picture identifier.",
            )

        old_key = profile.profile_picture_key
        profile.profile_picture_key = new_key
        await self.db.flush()

        return {
            "profile_picture_url": get_tutor_profile_picture_url(new_key),
            "old_key": old_key,
        }

    async def delete(self, user: User):
        if user.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tutor accounts can delete profile pictures.",
            )

        profile = await self.tutors.get_by_user_id_for_update(user.id)
        if not profile or not profile.profile_picture_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile picture not found.",
            )

        old_key = profile.profile_picture_key
        profile.profile_picture_key = None
        await self.db.flush()

        return old_key

    @staticmethod
    def delete_old_picture(old_key: str | None) -> None:
        if old_key:
            delete_tutor_profile_picture(old_key)
