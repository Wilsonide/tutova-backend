import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.verification.models.tutor_verification import TutorVerification


class VerificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_tutor_for_update(self, tutor_user_id):
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

    async def list_pending(self, limit: int = 50) -> list[TutorVerification]:
        result = await self.db.execute(
            select(TutorVerification)
            .where(TutorVerification.status == "PENDING_REVIEW")
            .order_by(TutorVerification.submitted_at.asc())
            .limit(limit)
        )
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
