import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.models.user import User, UserRole, UserStatus
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.verification.models.tutor_verification import TutorVerification


class AdminTutorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _base_query(self):
        return (
            select(
                User,
                TutorProfile,
                TutorVerification.status,
            )
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

    def _apply_filters(
        self,
        query,
        search: str | None = None,
        status: UserStatus | None = None,
    ):
        if status is not None:
            query = query.where(User.status == status)

        if search:
            search = search.strip()

            if search:
                pattern = f"%{search}%"

                query = query.where(
                    or_(
                        User.first_name.ilike(pattern),
                        User.last_name.ilike(pattern),
                        User.email.ilike(pattern),
                        User.phone_number.ilike(pattern),
                    )
                )

        return query

    async def list_tutors(
        self,
        page: int,
        per_page: int,
        search: str | None = None,
        status: UserStatus | None = None,
    ) -> tuple[list[tuple], int]:
        offset = (page - 1) * per_page

        query = self._apply_filters(
            self._base_query(),
            search=search,
            status=status,
        )

        count_query = select(func.count(User.id)).where(User.role == UserRole.TUTOR)

        if status is not None:
            count_query = count_query.where(User.status == status)

        if search:
            search = search.strip()

            if search:
                pattern = f"%{search}%"

                count_query = count_query.where(
                    or_(
                        User.first_name.ilike(pattern),
                        User.last_name.ilike(pattern),
                        User.email.ilike(pattern),
                        User.phone_number.ilike(pattern),
                    )
                )

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        result = await self.db.execute(
            query.order_by(User.created_at.desc()).offset(offset).limit(per_page)
        )

        return list(result.all()), total

    async def get_tutor(
        self,
        user_id: uuid.UUID,
    ) -> tuple | None:
        result = await self.db.execute(self._base_query().where(User.id == user_id))

        return result.one_or_none()

    async def get_user_for_update(
        self,
        user_id: uuid.UUID,
    ) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(
                User.id == user_id,
                User.role == UserRole.TUTOR,
            )
            .with_for_update()
        )

        return result.scalar_one_or_none()
