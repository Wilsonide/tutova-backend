from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cloudinary_service import (
    get_tutor_profile_picture_url,
)
from app.domain.authentication.models.user import User, UserRole
from app.domain.locations.models.location import Location
from app.domain.subjects.models.subject import Subject
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.tutors.repositories.tutor_repository import TutorRepository
from app.domain.tutors.schemas.tutor import (
    TutorProfileCreate,
    TutorProfileResponse,
    TutorProfileUpdate,
)


class TutorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tutors = TutorRepository(db)

    @staticmethod
    def _require_tutor(user: User) -> None:
        if user.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tutor accounts can perform this action.",
            )

    async def create_profile(
        self,
        user: User,
        data: TutorProfileCreate,
    ) -> TutorProfile:
        self._require_tutor(user)

        existing = await self.tutors.get_by_user_id(user.id)

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tutor profile already exists.",
            )

        profile = TutorProfile(
            user_id=user.id,
            **data.model_dump(),
        )

        return await self.tutors.create(profile)

    async def get_profile(self, user: User) -> TutorProfile:
        self._require_tutor(user)

        profile = await self.tutors.get_by_user_id_with_catalog(user.id)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tutor profile not found.",
            )

        return profile

    async def update_profile(
        self,
        user: User,
        data: TutorProfileUpdate,
    ) -> TutorProfile:
        profile = await self.get_profile(user)

        update_data = data.model_dump(exclude_unset=True)

        # Explicit nulls are not accepted for required profile fields.
        for field in (
            "years_of_experience",
            "monthly_fee",
            "teaching_languages",
            "learner_age_groups",
            "tutoring_modes",
        ):
            if field in update_data and update_data[field] is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field} cannot be null.",
                )

        return await self.tutors.update(profile, update_data)

    async def update_catalog_selection(self, user: User, data):
        self._require_tutor(user)

        profile = await self.tutors.get_by_user_id_for_update(user.id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tutor profile not found.",
            )

        subject_ids = data.subject_ids
        location_ids = data.location_ids

        if len(set(subject_ids)) != len(subject_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Duplicate subject IDs are not allowed.",
            )

        if len(set(location_ids)) != len(location_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Duplicate location IDs are not allowed.",
            )

        subject_result = (
            await self.db.execute(
                select(Subject).where(
                    Subject.id.in_(subject_ids),
                    Subject.is_active.is_(True),
                )
            )
            if subject_ids
            else None
        )

        subjects = list(subject_result.scalars().all()) if subject_result else []

        if len(subjects) != len(subject_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="One or more subjects are invalid or inactive.",
            )

        location_result = (
            await self.db.execute(
                select(Location).where(
                    Location.id.in_(location_ids),
                    Location.is_active.is_(True),
                )
            )
            if location_ids
            else None
        )

        locations = list(location_result.scalars().all()) if location_result else []

        if len(locations) != len(location_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="One or more locations are invalid or inactive.",
            )

        profile.subjects = subjects
        profile.locations = locations

        await self.db.flush()
        await self.db.refresh(profile)

        return profile

    async def get_profile_response(self, user: User):
        profile = await self.get_profile(user)

        response = TutorProfileResponse.model_validate(profile)

        return response.model_copy(
            update={
                "profile_picture_url": get_tutor_profile_picture_url(
                    profile.profile_picture_key
                ),
                "subject_ids": [subject.id for subject in profile.subjects],
                "location_ids": [location.id for location in profile.locations],
            }
        )
