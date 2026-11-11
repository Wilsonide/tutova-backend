import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.learners.models.learner_profile import LearnerProfile


class LearnerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
        self,
        learner_id: uuid.UUID,
    ) -> LearnerProfile | None:
        result = await self.db.execute(
            select(LearnerProfile).where(LearnerProfile.id == learner_id)
        )
        return result.scalar_one_or_none()

    async def get_parent_learner(
        self,
        learner_id: uuid.UUID,
        parent_profile_id: uuid.UUID,
    ) -> LearnerProfile | None:
        result = await self.db.execute(
            select(LearnerProfile).where(
                LearnerProfile.id == learner_id,
                LearnerProfile.parent_profile_id == parent_profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_parent(
        self,
        parent_profile_id: uuid.UUID,
    ) -> list[LearnerProfile]:
        result = await self.db.execute(
            select(LearnerProfile)
            .where(LearnerProfile.parent_profile_id == parent_profile_id)
            .order_by(LearnerProfile.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_user_id(
        self,
        user_id: uuid.UUID,
    ) -> LearnerProfile | None:
        result = await self.db.execute(
            select(LearnerProfile).where(LearnerProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        learner: LearnerProfile,
    ) -> LearnerProfile:
        self.db.add(learner)
        await self.db.flush()
        await self.db.refresh(learner)
        return learner

    async def update(
        self,
        learner: LearnerProfile,
        data: dict,
    ) -> LearnerProfile:
        for field, value in data.items():
            setattr(learner, field, value)

        await self.db.flush()
        await self.db.refresh(learner)
        return learner

    async def delete(self, learner: LearnerProfile) -> None:
        await self.db.delete(learner)
        await self.db.flush()
