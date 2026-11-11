import uuid
from math import ceil

from fastapi import HTTPException, status
from sqlalchemy import cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cloudinary_service import (
    get_tutor_profile_picture_url,
    get_tutor_video_url,
)
from app.domain.authentication.models.user import (
    User,
    UserRole,
    UserStatus,
)
from app.domain.locations.models.location import Location
from app.domain.subjects.models.subject import Subject
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.tutors.schemas.public_tutor import (
    PublicLocationResponse,
    PublicSubjectResponse,
    PublicTutorListResponse,
    PublicTutorResponse,
)
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)


class PublicTutorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _conditions(
        self,
        search: str | None,
        subject_id: uuid.UUID | None,
        location_id: uuid.UUID | None,
        tutoring_mode: str | None,
    ):
        conditions = [
            User.role == UserRole.TUTOR,
            User.status == UserStatus.ACTIVE,
            TutorVerification.status == VerificationStatus.APPROVED,
        ]

        if search:
            term = f"%{search.strip()}%"
            conditions.append(
                or_(
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                    TutorProfile.bio.ilike(term),
                    TutorProfile.qualifications.ilike(term),
                    TutorProfile.subjects.any(Subject.name.ilike(term)),
                )
            )

        if subject_id:
            conditions.append(TutorProfile.subjects.any(Subject.id == subject_id))

        if location_id:
            conditions.append(TutorProfile.locations.any(Location.id == location_id))

        if tutoring_mode:
            conditions.append(
                cast(TutorProfile.tutoring_modes, JSONB).contains([tutoring_mode])
            )

        return conditions

    @staticmethod
    def _to_response(
        profile: TutorProfile,
        user: User,
        verification: TutorVerification,
    ) -> PublicTutorResponse:
        subjects = [
            PublicSubjectResponse(
                id=subject.id,
                name=subject.name,
                slug=subject.slug,
            )
            for subject in profile.subjects
            if subject.is_active
        ]

        locations = [
            PublicLocationResponse(
                id=location.id,
                name=location.name,
                slug=location.slug,
                location_type=location.location_type.value,
            )
            for location in profile.locations
            if location.is_active
        ]

        return PublicTutorResponse(
            id=profile.id,
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=f"{user.first_name} {user.last_name}",
            bio=profile.bio,
            qualifications=profile.qualifications,
            years_of_experience=profile.years_of_experience,
            hourly_rate=(
                float(profile.hourly_rate) if profile.hourly_rate is not None else None
            ),
            teaching_languages=profile.teaching_languages,
            learner_age_groups=profile.learner_age_groups,
            tutoring_modes=profile.tutoring_modes,
            service_area=profile.service_area,
            subjects=subjects,
            profile_picture_url=get_tutor_profile_picture_url(
                profile.profile_picture_key
            ),
            locations=locations,
            introduction_video_url=get_tutor_video_url(
                verification.introduction_video_key
            ),
        )

    async def list_tutors(
        self,
        *,
        page: int = 1,
        per_page: int = 12,
        search: str | None = None,
        subject_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        tutoring_mode: str | None = None,
    ) -> PublicTutorListResponse:
        conditions = self._conditions(
            search,
            subject_id,
            location_id,
            tutoring_mode,
        )

        count_stmt = (
            select(func.count(TutorProfile.id))
            .join(User, User.id == TutorProfile.user_id)
            .join(
                TutorVerification,
                TutorVerification.tutor_user_id == User.id,
            )
            .where(*conditions)
        )

        total = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(TutorProfile, User, TutorVerification)
            .join(User, User.id == TutorProfile.user_id)
            .join(
                TutorVerification,
                TutorVerification.tutor_user_id == User.id,
            )
            .where(*conditions)
            .options(
                selectinload(TutorProfile.subjects),
                selectinload(TutorProfile.locations),
            )
            .order_by(TutorProfile.updated_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return PublicTutorListResponse(
            items=[
                self._to_response(profile, user, verification)
                for profile, user, verification in rows
            ],
            page=page,
            per_page=per_page,
            total=total,
            total_pages=ceil(total / per_page) if total else 0,
        )

    async def get_tutor(
        self,
        tutor_id: uuid.UUID,
    ) -> PublicTutorResponse:
        stmt = (
            select(TutorProfile, User, TutorVerification)
            .join(User, User.id == TutorProfile.user_id)
            .join(
                TutorVerification,
                TutorVerification.tutor_user_id == User.id,
            )
            .where(
                TutorProfile.id == tutor_id,
                User.role == UserRole.TUTOR,
                User.status == UserStatus.ACTIVE,
                TutorVerification.status == VerificationStatus.APPROVED,
            )
            .options(
                selectinload(TutorProfile.subjects),
                selectinload(TutorProfile.locations),
            )
        )

        result = await self.db.execute(stmt)
        row = result.one_or_none()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tutor not found.",
            )

        profile, user, verification = row

        return self._to_response(profile, user, verification)
