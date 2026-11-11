import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.authentication.models.user import (
    User,
    UserRole,
    UserStatus,
)
from app.domain.locations.models.location import Location
from app.domain.subjects.models.subject import Subject
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)


class PublicTutorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _base_conditions(
        self,
        search: str | None = None,
        subject_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        tutoring_mode: str | None = None,
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
            conditions.append(TutorProfile.tutoring_modes.contains([tutoring_mode]))

        return conditions

    async def list_public_tutors(
        self,
        *,
        page: int,
        per_page: int,
        search: str | None = None,
        subject_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        tutoring_mode: str | None = None,
    ):
        conditions = self._base_conditions(
            search=search,
            subject_id=subject_id,
            location_id=location_id,
            tutoring_mode=tutoring_mode,
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
            select(TutorProfile)
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

        return list(result.scalars().unique().all()), total

    async def get_public_tutor(
        self,
        tutor_id: uuid.UUID,
    ) -> TutorProfile | None:
        stmt = (
            select(TutorProfile)
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

        return result.scalars().unique().one_or_none()
