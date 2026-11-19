import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.authentication.models.user import User, UserRole
from app.domain.tutors.repositories.tutor_repository import TutorRepository
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)
from app.domain.verification.models.tutor_referee import TutorReferee, RefereeStatus
from app.domain.verification.repositories.verification_repository import (
    VerificationRepository,
)
from app.domain.verification.schemas.verification import (
    VerificationReviewRequest,
    VerificationSubmission,
)
from app.domain.verification.schemas.referee import SafeguardingReviewRequest


class VerificationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.verifications = VerificationRepository(db)
        self.tutors = TutorRepository(db)

    @staticmethod
    def _require_tutor(user: User) -> None:
        if user.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tutors can submit verification.",
            )

    @staticmethod
    def _require_admin(user: User) -> None:
        if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access is required.",
            )

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
        verification: TutorVerification,
    ) -> list[str]:
        missing: list[str] = []

        if profile is None or not profile.profile_picture_key:
            missing.append("profile_picture")

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

        return missing

    @staticmethod
    def _raise_incomplete(
        profile_fields: list[str],
        verification_fields: list[str],
    ) -> None:
        details: list[str] = []

        if profile_fields:
            details.append(
                "Complete these tutor profile fields first: "
                + ", ".join(profile_fields)
            )

        if verification_fields:
            details.append(
                "Complete these verification requirements: "
                + ", ".join(verification_fields)
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=" ".join(details),
        )

    async def submit(
        self,
        user: User,
        data: VerificationSubmission,
    ) -> TutorVerification:
        self._require_tutor(user)

        profile = await self.tutors.get_by_user_id_with_catalog(user.id)

        missing_profile_fields = self._missing_profile_fields(profile)

        if missing_profile_fields:
            self._raise_incomplete(missing_profile_fields, [])

        if not profile.profile_picture_key:
            self._raise_incomplete([], ["profile_picture"])

        if not data.accept_nda:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="You must accept the tutor NDA.",
            )

        verification = await self.verifications.get_by_tutor_for_update(user.id)

        if verification is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Upload your identity document and introduction video "
                    "before submitting verification."
                ),
            )

        referees = list((await self.db.scalars(
            select(TutorReferee).where(TutorReferee.tutor_user_id == user.id)
        )).all())
        invited_referees = [
            referee for referee in referees if referee.invitation_sent_at is not None
        ]
        if len(invited_referees) < 2:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Submit at least two referee records and ensure their email "
                    "invitations have been sent before submitting tutor verification."
                ),
            )

        if verification.status in (
            VerificationStatus.PENDING_REVIEW,
            VerificationStatus.APPROVED,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Verification is already pending or approved.",
            )

        missing_verification_fields = self._missing_verification_fields(
            profile,
            verification,
        )

        # These fields are populated by this submission operation.
        fields_populated_on_submit = {
            "identity_document_type",
            "nda_version",
            "nda_accepted_at",
            "submitted_at",
        }

        missing_verification_fields = [
            field
            for field in missing_verification_fields
            if field not in fields_populated_on_submit
        ]

        if missing_verification_fields:
            self._raise_incomplete([], missing_verification_fields)

        now = datetime.now(timezone.utc)

        verification.identity_document_type = data.identity_document_type
        verification.nda_version = settings.CURRENT_NDA_VERSION
        verification.nda_accepted_at = now
        verification.submitted_at = now
        verification.status = VerificationStatus.PENDING_REVIEW
        verification.reviewed_by = None
        verification.reviewed_at = None
        verification.review_notes = None

        return await self.verifications.save(verification)

    async def get_my_status(self, user: User) -> TutorVerification:
        self._require_tutor(user)

        verification = await self.verifications.get_by_tutor(user.id)

        if verification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification submission not found.",
            )

        return verification

    async def list_pending(
        self,
        admin: User,
        limit: int = 50,
    ) -> list[TutorVerification]:
        self._require_admin(admin)

        return await self.verifications.list_pending(limit=max(1, min(limit, 100)))

    async def review(
        self,
        admin: User,
        verification_id: uuid.UUID,
        data: VerificationReviewRequest,
    ) -> TutorVerification:
        self._require_admin(admin)

        verification = await self.verifications.get_by_id_for_update(verification_id)

        if verification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification submission not found.",
            )

        if verification.status != VerificationStatus.PENDING_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending submissions can be reviewed.",
            )

        if data.decision == "APPROVED":
            if verification.safeguarding_review_required:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This tutor has an outstanding safeguarding review. "
                        "Complete the safeguarding review before approving the application."
                    ),
                )

            referee_records = list((await self.db.scalars(
                select(TutorReferee).where(
                    TutorReferee.tutor_user_id == verification.tutor_user_id
                )
            )).all())
            consented_referees = [
                referee for referee in referee_records
                if referee.status == RefereeStatus.CONSENTED
            ]
            if len(consented_referees) < 2:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "At least two referees must consent before this tutor "
                        "application can be approved. Review the referee responses first."
                    ),
                )

            profile = await self.tutors.get_by_user_id_with_catalog(
                verification.tutor_user_id
            )

            missing_profile_fields = self._missing_profile_fields(profile)
            missing_verification_fields = self._missing_verification_fields(
                profile, verification
            )

            if missing_profile_fields or missing_verification_fields:
                self._raise_incomplete(
                    missing_profile_fields,
                    missing_verification_fields,
                )

        if data.decision in ("REJECTED", "CHANGES_REQUESTED"):
            if not data.review_notes or not data.review_notes.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Review notes are required for this decision.",
                )

        verification.status = VerificationStatus(data.decision)
        verification.reviewed_by = admin.id
        verification.reviewed_at = datetime.now(timezone.utc)
        verification.review_notes = (
            data.review_notes.strip() if data.review_notes else None
        )

        return await self.verifications.save(verification)


    async def review_safeguarding_flag(
        self,
        admin: User,
        verification_id: uuid.UUID,
        data: SafeguardingReviewRequest,
    ) -> TutorVerification:
        self._require_admin(admin)
        verification = await self.verifications.get_by_id_for_update(verification_id)
        if verification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification submission not found.",
            )
        if not verification.safeguarding_review_required:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This tutor has no outstanding safeguarding flag.",
            )

        verification.safeguarding_reviewed_by = admin.id
        verification.safeguarding_reviewed_at = datetime.now(timezone.utc)
        verification.safeguarding_review_notes = data.review_notes
        if data.decision == "CLEAR":
            verification.safeguarding_review_required = False
            verification.safeguarding_review_reasons = []

        return await self.verifications.save(verification)
