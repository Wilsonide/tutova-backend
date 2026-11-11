import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.tutors.models.tutor_profile import TutorProfile


class TutorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(
        self,
        user_id: uuid.UUID,
    ) -> TutorProfile | None:
        result = await self.db.execute(
            select(TutorProfile).where(TutorProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id_with_catalog(
        self,
        user_id: uuid.UUID,
    ) -> TutorProfile | None:
        result = await self.db.execute(
            select(TutorProfile)
            .where(TutorProfile.user_id == user_id)
            .options(
                selectinload(TutorProfile.subjects),
                selectinload(TutorProfile.locations),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        profile: TutorProfile,
    ) -> TutorProfile:
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def update(
        self,
        profile: TutorProfile,
        data: dict,
    ) -> TutorProfile:
        for field, value in data.items():
            setattr(profile, field, value)

        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def get_by_user_id_for_update(
        self,
        user_id: uuid.UUID,
    ) -> TutorProfile | None:
        result = await self.db.execute(
            select(TutorProfile)
            .where(TutorProfile.user_id == user_id)
            .options(
                selectinload(TutorProfile.subjects),
                selectinload(TutorProfile.locations),
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()
