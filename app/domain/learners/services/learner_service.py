from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.models.user import User, UserRole
from app.domain.learners.models.learner_profile import LearnerProfile
from app.domain.learners.repositories.learner_repository import LearnerRepository
from app.domain.learners.schemas.learner import (
    LearnerProfileCreate,
    LearnerProfileUpdate,
)


class LearnerService:
    def __init__(self, db: AsyncSession):
        self.learners = LearnerRepository(db)

    @staticmethod
    def _require_adult_learner(user: User) -> None:
        if user.role != UserRole.ADULT_LEARNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only adult learner accounts can perform this action.",
            )

    async def create_profile(
        self,
        user: User,
        data: LearnerProfileCreate,
    ) -> LearnerProfile:
        self._require_adult_learner(user)

        existing = await self.learners.get_by_user_id(user.id)

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Learner profile already exists.",
            )

        learner = LearnerProfile(
            user_id=user.id,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
        )

        return await self.learners.create(learner)

    async def get_profile(self, user: User) -> LearnerProfile:
        self._require_adult_learner(user)

        learner = await self.learners.get_by_user_id(user.id)

        if not learner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
            )

        return learner

    async def update_profile(
        self,
        user: User,
        data: LearnerProfileUpdate,
    ) -> LearnerProfile:
        learner = await self.get_profile(user)
        update_data = data.model_dump(exclude_unset=True)

        for field in ("first_name", "last_name"):
            if field in update_data and update_data[field] is not None:
                update_data[field] = update_data[field].strip()

        return await self.learners.update(learner, update_data)
