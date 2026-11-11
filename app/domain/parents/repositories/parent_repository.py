import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.parents.models.parent_profile import ParentProfile


class ParentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(
        self,
        user_id: uuid.UUID,
    ) -> ParentProfile | None:
        result = await self.db.execute(
            select(ParentProfile).where(ParentProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        profile: ParentProfile,
    ) -> ParentProfile:
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile
