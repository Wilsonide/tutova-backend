import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cloudinary_service import get_tutor_profile_picture_url
from app.domain.authentication.models.user import UserStatus
from app.domain.tutors.repositories.admin_tutor_repository import (
    AdminTutorRepository,
)
from app.domain.tutors.schemas.admin_tutor import (
    AdminTutorListResponse,
    AdminTutorProfileResponse,
    AdminTutorResponse,
)


class AdminTutorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = AdminTutorRepository(db)

    @staticmethod
    def _build_response(row: tuple) -> AdminTutorResponse:
        user, profile, verification_status = row

        profile_response = None

        if profile is not None:
            profile_response = AdminTutorProfileResponse.model_validate(
                profile
            ).model_copy(
                update={
                    "profile_picture_url": get_tutor_profile_picture_url(
                        profile.profile_picture_key
                    )
                }
            )

        return AdminTutorResponse(
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            phone_number=user.phone_number,
            role=user.role,
            account_type=user.account_type,
            status=user.status,
            is_email_verified=user.is_email_verified,
            is_phone_verified=user.is_phone_verified,
            must_change_password=user.must_change_password,
            created_at=user.created_at,
            verification_status=verification_status,
            tutor_profile=profile_response,
        )

    async def list_tutors(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        account_status: UserStatus | None = None,
    ) -> AdminTutorListResponse:
        rows, total = await self.repository.list_tutors(
            page=page,
            per_page=per_page,
            search=search,
            status=account_status,
        )

        return AdminTutorListResponse(
            items=[self._build_response(row) for row in rows],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total / per_page) if total else 0,
        )

    async def get_tutor(
        self,
        user_id: uuid.UUID,
    ) -> AdminTutorResponse:
        row = await self.repository.get_tutor(user_id)

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tutor account not found.",
            )

        return self._build_response(row)

    async def update_tutor_status(
        self,
        user_id: uuid.UUID,
        new_status: UserStatus,
    ) -> AdminTutorResponse:
        user = await self.repository.get_user_for_update(user_id)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tutor account not found.",
            )

        if user.status == new_status:
            return await self.get_tutor(user_id)

        user.status = new_status

        await self.db.flush()

        return await self.get_tutor(user_id)
