import uuid

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.authentication.models.user import User, UserRole, UserStatus
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)


class AdminTutorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def profile_complete_condition():
        return and_(
            TutorProfile.id.is_not(None),
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
    def verification_materials_complete_condition():
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

    @classmethod
    def ready_for_verification_condition(cls):
        return and_(
            cls.profile_complete_condition(),
            cls.verification_materials_complete_condition(),
            TutorVerification.status == VerificationStatus.PENDING_REVIEW,
        )

    def _base_query(self):
        return (
            select(User, TutorProfile, TutorVerification)
            .outerjoin(
                TutorProfile,
                TutorProfile.user_id == User.id,
            )
            .outerjoin(
                TutorVerification,
                TutorVerification.tutor_user_id == User.id,
            )
            .options(
                selectinload(TutorProfile.subjects),
                selectinload(TutorProfile.locations),
            )
            .where(User.role == UserRole.TUTOR)
        )

    def _apply_filters(
        self,
        query,
        search: str | None = None,
        status: UserStatus | None = None,
        profile_completion: str | None = None,
        verification_completion: str | None = None,
    ):
        if status is not None:
            query = query.where(User.status == status)

        if search:
            pattern = f"%{search.strip()}%"
            if pattern != "%%":
                query = query.where(
                    or_(
                        User.first_name.ilike(pattern),
                        User.last_name.ilike(pattern),
                        User.email.ilike(pattern),
                        User.phone_number.ilike(pattern),
                    )
                )

        profile_complete = self.profile_complete_condition()
        verification_ready = self.ready_for_verification_condition()

        if profile_completion == "complete":
            query = query.where(profile_complete)
        elif profile_completion == "incomplete":
            query = query.where(not_(profile_complete))

        if verification_completion == "complete":
            query = query.where(verification_ready)

        elif verification_completion == "incomplete":
            query = query.where(
                profile_complete,
                not_(verification_ready),
                or_(
                    TutorVerification.status.is_(None),
                    TutorVerification.status != VerificationStatus.APPROVED,
                ),
            )

        return query

    async def list_tutors(
        self,
        page: int,
        per_page: int,
        search: str | None = None,
        status: UserStatus | None = None,
        profile_completion: str | None = None,
        verification_completion: str | None = None,
    ) -> tuple[list[tuple], int]:
        offset = (page - 1) * per_page

        query = self._apply_filters(
            self._base_query(),
            search=search,
            status=status,
            profile_completion=profile_completion,
            verification_completion=verification_completion,
        )

        count_query = (
            select(func.count(User.id))
            .select_from(User)
            .outerjoin(
                TutorProfile,
                TutorProfile.user_id == User.id,
            )
            .outerjoin(
                TutorVerification,
                TutorVerification.tutor_user_id == User.id,
            )
            .where(User.role == UserRole.TUTOR)
        )

        count_query = self._apply_filters(
            count_query,
            search=search,
            status=status,
            profile_completion=profile_completion,
            verification_completion=verification_completion,
        )

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        result = await self.db.execute(
            query.order_by(User.created_at.desc()).offset(offset).limit(per_page)
        )

        return list(result.all()), total

    async def get_tutor(self, user_id: uuid.UUID) -> tuple | None:
        result = await self.db.execute(self._base_query().where(User.id == user_id))
        return result.one_or_none()

    async def get_user_for_update(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(
                User.id == user_id,
                User.role == UserRole.TUTOR,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()
