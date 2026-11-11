from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cloudinary_service import (
    ALLOWED_IDENTITY_DOCUMENT_TYPES,
    delete_tutor_identity_document,
    get_identity_document_download_url,
    upload_tutor_identity_document,
)
from app.core.config import settings
from app.domain.authentication.models.user import User, UserRole
from app.domain.tutors.repositories.tutor_repository import TutorRepository
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)
from app.domain.verification.repositories.verification_repository import (
    VerificationRepository,
)


class IdentityDocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tutors = TutorRepository(db)
        self.verifications = VerificationRepository(db)

    @staticmethod
    def _require_tutor(user: User) -> None:
        if user.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tutors can upload identity documents.",
            )

    @staticmethod
    def _require_admin(user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access is required.",
            )

    async def upload(self, user: User, file):
        self._require_tutor(user)

        profile = await self.tutors.get_by_user_id(user.id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Create your tutor profile before uploading an identity document.",
            )

        content_type = file.content_type
        if content_type not in ALLOWED_IDENTITY_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Identity documents must be PDF, JPEG, or PNG files.",
            )

        content = await file.read(settings.CLOUDINARY_IDENTITY_DOCUMENT_MAX_SIZE + 1)

        if not content:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The uploaded identity document is empty.",
            )

        if len(content) > settings.CLOUDINARY_IDENTITY_DOCUMENT_MAX_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Identity documents must not exceed 10 MB.",
            )

        verification = await self.verifications.get_by_tutor_for_update(user.id)

        if verification and verification.status in (
            VerificationStatus.PENDING_REVIEW,
            VerificationStatus.APPROVED,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "You cannot replace your identity document while "
                    "verification is pending or approved."
                ),
            )

        uploaded = upload_tutor_identity_document(
            content=content,
            tutor_user_id=str(user.id),
            content_type=content_type,
        )

        new_key = uploaded["public_id"]
        file_format = uploaded["format"]

        old_key = verification.identity_document_key if verification else None

        if not verification:
            verification = TutorVerification(
                tutor_user_id=user.id,
                status=VerificationStatus.NOT_SUBMITTED,
            )
            self.db.add(verification)

        verification.identity_document_key = new_key
        verification.identity_document_type = None
        verification.identity_document_format = file_format

        await self.db.flush()

        return {
            "old_key": old_key,
            "message": "Identity document uploaded securely.",
        }

    async def get_admin_download_url(
        self,
        admin: User,
        verification_id,
    ) -> str:
        self._require_admin(admin)

        verification = await self.verifications.get_by_id(verification_id)

        if not verification or not verification.identity_document_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Identity document not found.",
            )

        return get_identity_document_download_url(
            verification.identity_document_key,
            verification.identity_document_format,
        )

    @staticmethod
    def delete_old_document(old_key: str | None) -> None:
        if old_key:
            delete_tutor_identity_document(old_key)
