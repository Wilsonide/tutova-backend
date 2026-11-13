import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)


class VerificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_tutor_for_update(
        self,
        tutor_user_id: uuid.UUID,
    ) -> TutorVerification | None:
        result = await self.db.execute(
            select(TutorVerification)
            .where(TutorVerification.tutor_user_id == tutor_user_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_tutor(
        self,
        tutor_user_id: uuid.UUID,
    ) -> TutorVerification | None:
        result = await self.db.execute(
            select(TutorVerification).where(
                TutorVerification.tutor_user_id == tutor_user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        verification_id: uuid.UUID,
    ) -> TutorVerification | None:
        result = await self.db.execute(
            select(TutorVerification).where(TutorVerification.id == verification_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(
        self,
        verification_id: uuid.UUID,
    ) -> TutorVerification | None:
        result = await self.db.execute(
            select(TutorVerification)
            .where(TutorVerification.id == verification_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _profile_complete_condition():
        return and_(
            func.length(func.trim(TutorProfile.bio)) > 0,
            func.length(func.trim(TutorProfile.qualifications)) > 0,
            func.coalesce(func.json_array_length(TutorProfile.teaching_languages), 0)
            > 0,
            func.coalesce(func.json_array_length(TutorProfile.learner_age_groups), 0)
            > 0,
            func.coalesce(func.json_array_length(TutorProfile.tutoring_modes), 0) > 0,
            TutorProfile.subjects.any(),
            TutorProfile.locations.any(),
        )

    @staticmethod
    def _verification_materials_complete_condition():
        return and_(
            func.length(func.trim(TutorProfile.profile_picture_key)) > 0,
            func.length(func.trim(TutorVerification.identity_document_key)) > 0,
            func.length(func.trim(TutorVerification.identity_document_format)) > 0,
            func.length(func.trim(TutorVerification.identity_document_type)) > 0,
            func.length(func.trim(TutorVerification.introduction_video_key)) > 0,
            func.length(func.trim(TutorVerification.nda_version)) > 0,
            TutorVerification.nda_accepted_at.is_not(None),
            TutorVerification.submitted_at.is_not(None),
        )

    async def list_pending(self, limit: int = 50) -> list[TutorVerification]:
        query = (
            select(TutorVerification)
            .join(
                TutorProfile,
                TutorProfile.user_id == TutorVerification.tutor_user_id,
            )
            .where(
                TutorVerification.status == VerificationStatus.PENDING_REVIEW,
                self._profile_complete_condition(),
                self._verification_materials_complete_condition(),
            )
            .order_by(TutorVerification.submitted_at.asc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(
        self,
        verification: TutorVerification,
    ) -> TutorVerification:
        self.db.add(verification)
        await self.db.flush()
        await self.db.refresh(verification)
        return verification

    async def save(
        self,
        verification: TutorVerification,
    ) -> TutorVerification:
        await self.db.flush()
        await self.db.refresh(verification)
        return verification
