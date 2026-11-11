from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.models.user import User, UserRole
from app.domain.learners.models.learner_profile import LearnerProfile
from app.domain.learners.repositories.learner_repository import LearnerRepository
from app.domain.learners.schemas.learner import (
    LearnerProfileCreate,
    LearnerProfileUpdate,
)
from app.domain.parents.models.parent_profile import ParentProfile
from app.domain.parents.repositories.parent_repository import ParentRepository


class ParentService:
    def __init__(self, db: AsyncSession):
        self.parents = ParentRepository(db)
        self.learners = LearnerRepository(db)

    @staticmethod
    def _require_parent(user: User) -> None:
        if user.role != UserRole.PARENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only parent accounts can perform this action.",
            )

    async def create_profile(self, user: User) -> ParentProfile:
        self._require_parent(user)

        existing = await self.parents.get_by_user_id(user.id)

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Parent profile already exists.",
            )

        return await self.parents.create(ParentProfile(user_id=user.id))

    async def get_profile(self, user: User) -> ParentProfile:
        self._require_parent(user)

        profile = await self.parents.get_by_user_id(user.id)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent profile not found.",
            )

        return profile

    async def add_learner(
        self,
        user: User,
        data: LearnerProfileCreate,
    ) -> LearnerProfile:
        parent = await self.get_profile(user)

        learner = LearnerProfile(
            parent_profile_id=parent.id,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
        )

        return await self.learners.create(learner)

    async def list_learners(
        self,
        user: User,
    ) -> list[LearnerProfile]:
        parent = await self.get_profile(user)
        return await self.learners.get_by_parent(parent.id)

    async def get_learner(
        self,
        user: User,
        learner_id,
    ) -> LearnerProfile:
        parent = await self.get_profile(user)

        learner = await self.learners.get_parent_learner(
            learner_id=learner_id,
            parent_profile_id=parent.id,
        )

        if not learner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
            )

        return learner

    async def update_learner(
        self,
        user: User,
        learner_id,
        data: LearnerProfileUpdate,
    ) -> LearnerProfile:
        learner = await self.get_learner(user, learner_id)

        update_data = data.model_dump(exclude_unset=True)

        for field in ("first_name", "last_name"):
            if field in update_data and update_data[field] is not None:
                update_data[field] = update_data[field].strip()

        return await self.learners.update(learner, update_data)

    async def delete_learner(
        self,
        user: User,
        learner_id,
    ) -> None:
        learner = await self.get_learner(user, learner_id)
        await self.learners.delete(learner)
