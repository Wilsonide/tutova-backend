import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.domain.verification.schemas.verification import (
    VerificationReviewRequest,
    VerificationSubmission,
)


class VerificationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.verifications = VerificationRepository(db)
        self.tutors = TutorRepository(db)

    @staticmethod
    def _require_tutor(user: User) -> None:
        if user.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tutors can submit verification.",
            )

    @staticmethod
    def _require_admin(user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access is required.",
            )

    async def submit(
        self,
        user: User,
        data: VerificationSubmission,
    ) -> TutorVerification:
        self._require_tutor(user)

        profile = await self.tutors.get_by_user_id(user.id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Create your tutor profile before submitting verification.",
            )

        if not data.accept_nda:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="You must accept the tutor NDA.",
            )

        existing = await self.verifications.get_by_tutor_for_update(user.id)

        if not existing or not existing.introduction_video_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Upload your introduction video before submitting verification.",
            )

        if not existing.identity_document_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Upload your identity document before submitting verification.",
            )

        if not existing.identity_document_format:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Your identity document upload is incomplete. Upload it again.",
            )

        if existing.status in (
            VerificationStatus.PENDING_REVIEW,
            VerificationStatus.APPROVED,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Verification is already pending or approved.",
            )

        now = datetime.now(timezone.utc)

        existing.identity_document_type = data.identity_document_type
        existing.nda_version = settings.CURRENT_NDA_VERSION
        existing.nda_accepted_at = now
        existing.submitted_at = now
        existing.status = VerificationStatus.PENDING_REVIEW
        existing.reviewed_by = None
        existing.reviewed_at = None
        existing.review_notes = None

        return await self.verifications.save(existing)

    async def get_my_status(self, user: User) -> TutorVerification:
        self._require_tutor(user)

        verification = await self.verifications.get_by_tutor(user.id)

        if not verification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification submission not found.",
            )

        return verification

    async def list_pending(
        self,
        admin: User,
        limit: int = 50,
    ) -> list[TutorVerification]:
        self._require_admin(admin)
        return await self.verifications.list_pending(limit=max(1, min(limit, 100)))

    async def review(
        self,
        admin: User,
        verification_id: uuid.UUID,
        data: VerificationReviewRequest,
    ) -> TutorVerification:
        self._require_admin(admin)

        verification = await self.verifications.get_by_id(verification_id)

        if not verification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification submission not found.",
            )

        if verification.status != VerificationStatus.PENDING_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending submissions can be reviewed.",
            )

        if data.decision in ("REJECTED", "CHANGES_REQUESTED"):
            if not data.review_notes or not data.review_notes.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Review notes are required for this decision.",
                )

        verification.status = VerificationStatus(data.decision)
        verification.reviewed_by = admin.id
        verification.reviewed_at = datetime.now(timezone.utc)
        verification.review_notes = (
            data.review_notes.strip() if data.review_notes else None
        )

        return await self.verifications.save(verification)
