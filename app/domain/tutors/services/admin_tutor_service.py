import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cloudinary_service import get_tutor_profile_picture_url
from app.domain.authentication.models.user import User, UserStatus
from app.domain.tutors.repositories.admin_tutor_repository import (
    AdminTutorRepository,
)
from app.domain.tutors.schemas.admin_tutor import (
    AdminTutorListResponse,
    AdminTutorProfileResponse,
    AdminTutorResponse,
)
from app.domain.verification.models.tutor_verification import (
    VerificationStatus,
)


class AdminTutorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = AdminTutorRepository(db)

    @staticmethod
    def _missing_profile_fields(profile) -> list[str]:
        if profile is None:
            return [
                "bio",
                "qualifications",
                "teaching_languages",
                "learner_age_groups",
                "tutoring_modes",
                "subjects",
                "locations",
            ]

        missing: list[str] = []

        if not profile.bio or not profile.bio.strip():
            missing.append("bio")

        if not profile.qualifications or not profile.qualifications.strip():
            missing.append("qualifications")

        if not profile.teaching_languages:
            missing.append("teaching_languages")

        if not profile.learner_age_groups:
            missing.append("learner_age_groups")

        if not profile.tutoring_modes:
            missing.append("tutoring_modes")

        if not profile.subjects:
            missing.append("subjects")

        if not profile.locations:
            missing.append("locations")

        return missing

    @staticmethod
    def _missing_verification_fields(
        profile,
        verification,
    ) -> list[str]:
        missing: list[str] = []

        if profile is None or not profile.profile_picture_key:
            missing.append("profile_picture")

        if verification is None:
            return missing + [
                "identity_document",
                "identity_document_format",
                "identity_document_type",
                "introduction_video",
                "nda_version",
                "nda_accepted_at",
                "submitted_at",
            ]

        if not verification.identity_document_key:
            missing.append("identity_document")

        if not verification.identity_document_format:
            missing.append("identity_document_format")

        if not verification.identity_document_type:
            missing.append("identity_document_type")

        if not verification.introduction_video_key:
            missing.append("introduction_video")

        if not verification.nda_version:
            missing.append("nda_version")

        if not verification.nda_accepted_at:
            missing.append("nda_accepted_at")

        if not verification.submitted_at:
            missing.append("submitted_at")

        if verification.status in (
            VerificationStatus.CHANGES_REQUESTED,
            VerificationStatus.REJECTED,
        ):
            missing.append("resubmit_verification")

        return missing

    @classmethod
    def _build_response(cls, row: tuple) -> AdminTutorResponse:
        user, profile, verification = row

        missing_profile_fields = cls._missing_profile_fields(profile)
        missing_verification_fields = cls._missing_verification_fields(
            profile,
            verification,
        )

        profile_completed = not missing_profile_fields
        verification_completed = not missing_verification_fields

        verification_status = verification.status if verification else None

        ready_for_verification = (
            profile_completed
            and verification_completed
            and verification_status == VerificationStatus.PENDING_REVIEW
        )

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
            profile_completed=profile_completed,
            missing_profile_fields=missing_profile_fields,
            verification_completed=verification_completed,
            missing_verification_fields=missing_verification_fields,
            ready_for_verification=ready_for_verification,
        )

    async def list_tutors(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        account_status: UserStatus | None = None,
        profile_completion: str | None = None,
        verification_completion: str | None = None,
    ) -> AdminTutorListResponse:
        rows, total = await self.repository.list_tutors(
            page=page,
            per_page=per_page,
            search=search,
            status=account_status,
            profile_completion=profile_completion,
            verification_completion=verification_completion,
        )

        return AdminTutorListResponse(
            items=[self._build_response(row) for row in rows],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total / per_page) if total else 0,
        )

    async def get_tutor(self, user_id: uuid.UUID) -> AdminTutorResponse:
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
