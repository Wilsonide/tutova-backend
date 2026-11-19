import asyncio
import hashlib
import secrets
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.authentication.models.user import User, UserRole
from app.domain.verification.models.tutor_referee import RefereeStatus, TutorReferee
from app.domain.verification.models.tutor_verification import (
    TutorVerification,
    VerificationStatus,
)
from app.domain.verification.repositories.referee_repository import RefereeRepository
from app.domain.verification.repositories.verification_repository import (
    VerificationRepository,
)
from app.domain.verification.schemas.referee import (
    AdminTutorRefereeResponse,
    RefereeConsentPageResponse,
    RefereeConsentSubmission,
    TutorRefereeInviteRequest,
    TutorRefereeResponse,
)

CONSENT_TEXT = (
    "I confirm that I know the tutor named in this invitation, agree to act as a referee, "
    "and consent to Tutova contacting me to verify the information provided by the tutor. "
    "I understand that my response will be used for tutor onboarding and safeguarding review."
)


class RefereeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = RefereeRepository(db)
        self.verifications = VerificationRepository(db)

    @staticmethod
    def _require_tutor(user: User) -> None:
        if user.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=403, detail="Only tutors can manage referees."
            )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _send_email_sync(
        *,
        recipient: str,
        referee_name: str,
        referee_job_title: str,
        tutor_name: str,
        link: str,
    ) -> None:
        message = EmailMessage()
        message["Subject"] = f"Reference Request for {tutor_name} – Tutova"
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = recipient

        message.set_content(
            f"Hello {referee_name},\n\n"
            f"{tutor_name} has applied to become a tutor on Tutova "
            "and listed you as one of their referees.\n\n"
            "Because safety and trust are at the heart of our learning "
            "community, we verify every tutor before they begin teaching. "
            "We would appreciate a few minutes of your time to confirm your "
            f"relationship with {tutor_name} and complete a brief reference check.\n\n"
            "Please click the secure link below to review and submit your response:\n"
            f"{link}\n\n"
            "For your security, this link is private and will expire in "
            "7 days. If you were not expecting this request or do not know "
            "the applicant, you may safely ignore this email.\n\n"
            "Thank you for helping us keep learning safe for every child.\n\n"
            "Warm regards,\n\n"
            "The Tutova Safeguarding Team"
        )

        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=20,
        ) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()

            if settings.SMTP_USERNAME:
                smtp.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD,
                )

            smtp.send_message(message)

    async def invite(
        self, tutor: User, payload: TutorRefereeInviteRequest
    ) -> list[TutorRefereeResponse]:
        self._require_tutor(tutor)
        if not all((settings.SMTP_HOST, settings.SMTP_FROM_EMAIL)):
            raise HTTPException(
                status_code=503,
                detail="Referee email delivery is not configured. Set SMTP_HOST and SMTP_FROM_EMAIL before sending invitations.",
            )

        existing = await self.repository.list_for_tutor(tutor.id)
        submitted_emails = {
            str(item.email).strip().lower() for item in payload.referees
        }
        if any(
            referee.status == RefereeStatus.CONSENTED
            and referee.email not in submitted_emails
            for referee in existing
        ):
            raise HTTPException(
                status_code=409,
                detail="A referee who has already consented cannot be replaced in this onboarding submission.",
            )

        existing_by_email = {referee.email.lower(): referee for referee in existing}
        tokens_to_send: list[tuple[TutorReferee, str]] = []
        now = datetime.now(timezone.utc)
        tutor_name = f"{tutor.first_name} {tutor.last_name}".strip()

        for item in payload.referees:
            email = str(item.email).strip().lower()
            referee = existing_by_email.get(email)
            if referee is not None and referee.status == RefereeStatus.CONSENTED:
                # Preserve the referee's consented identity/details as an audit record.
                continue

            details_unchanged = (
                referee is not None
                and referee.full_name == item.full_name.strip()
                and referee.job_title == item.job_title.strip()
                and referee.relationship_to_tutor == item.relationship_to_tutor.strip()
            )
            if (
                referee is not None
                and referee.status == RefereeStatus.PENDING
                and referee.invitation_sent_at is not None
                and referee.token_expires_at > now
                and details_unchanged
            ):
                continue

            raw_token = secrets.token_urlsafe(36)
            if referee is None:
                referee = TutorReferee(
                    tutor_user_id=tutor.id,
                    full_name=item.full_name.strip(),
                    email=email,
                    job_title=item.job_title.strip(),
                    relationship_to_tutor=item.relationship_to_tutor.strip(),
                    consent_token_hash=self._token_hash(raw_token),
                    token_expires_at=now + timedelta(days=14),
                    status=RefereeStatus.PENDING,
                )
                self.db.add(referee)
            else:
                referee.full_name = item.full_name.strip()
                referee.job_title = item.job_title.strip()
                referee.relationship_to_tutor = item.relationship_to_tutor.strip()
                referee.consent_token_hash = self._token_hash(raw_token)
                referee.token_expires_at = now + timedelta(days=7)
                referee.invitation_sent_at = None
                referee.status = RefereeStatus.PENDING
            tokens_to_send.append((referee, raw_token))

        for referee in existing:
            if (
                referee.email.lower() not in submitted_emails
                and referee.status != RefereeStatus.CONSENTED
            ):
                await self.db.delete(referee)

        await self.db.commit()
        frontend_base = settings.FRONTEND_BASE_URL.rstrip("/")
        sent_ids: set[uuid.UUID] = set()
        try:
            for referee, token in tokens_to_send:
                link = f"{frontend_base}/referee-consent/{token}"
                await asyncio.to_thread(
                    self._send_email_sync,
                    recipient=referee.email,
                    referee_name=referee.full_name,
                    referee_job_title=referee.job_title,
                    tutor_name=tutor_name,
                    link=link,
                )
                referee.invitation_sent_at = datetime.now(timezone.utc)
                sent_ids.add(referee.id)
            await self.db.commit()
        except Exception as exc:
            await self.db.commit()
            raise HTTPException(
                status_code=502,
                detail=(
                    f"A referee invitation could not be delivered. {len(sent_ids)} invitation(s) were sent; "
                    "submit the referee details again to resend pending invitations."
                ),
            ) from exc

        return [
            TutorRefereeResponse.model_validate(item)
            for item in await self.repository.list_for_tutor(tutor.id)
        ]

    async def _mark_expired(self, referees: list[TutorReferee]) -> None:
        now = datetime.now(timezone.utc)
        changed = False
        for referee in referees:
            if (
                referee.status == RefereeStatus.PENDING
                and referee.token_expires_at <= now
            ):
                referee.status = RefereeStatus.EXPIRED
                referee.consent_token_hash = None
                changed = True
        if changed:
            await self.db.commit()

    async def list_mine(self, tutor: User) -> list[TutorRefereeResponse]:
        self._require_tutor(tutor)
        records = await self.repository.list_for_tutor(tutor.id)
        await self._mark_expired(records)
        return [TutorRefereeResponse.model_validate(item) for item in records]

    async def list_for_verification_admin(
        self, admin: User, verification_id: uuid.UUID
    ) -> list[AdminTutorRefereeResponse]:
        if admin.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(
                status_code=403, detail="Administrator access is required."
            )
        from app.domain.verification.models.tutor_verification import (
            TutorVerification,
            VerificationStatus,
        )

        verification = await self.db.get(TutorVerification, verification_id)
        if verification is None:
            raise HTTPException(status_code=404, detail="Tutor verification not found.")
        records = await self.repository.list_for_tutor(verification.tutor_user_id)
        await self._mark_expired(records)
        return [AdminTutorRefereeResponse.model_validate(item) for item in records]

    async def get_consent_page(self, token: str) -> RefereeConsentPageResponse:
        referee = await self.repository.get_by_token_hash(self._token_hash(token))
        if referee is None:
            raise HTTPException(
                status_code=404, detail="This referee invitation is invalid."
            )
        if (
            referee.token_expires_at <= datetime.now(timezone.utc)
            and referee.status == RefereeStatus.PENDING
        ):
            referee.status = RefereeStatus.EXPIRED
            referee.consent_token_hash = None
            await self.db.commit()
            raise HTTPException(
                status_code=410, detail="This referee invitation has expired."
            )
        tutor = await self.db.get(User, referee.tutor_user_id)
        tutor_name = (
            f"{tutor.first_name} {tutor.last_name}".strip() if tutor else "Tutova tutor"
        )
        return self._consent_page_response(referee, tutor_name)

    @staticmethod
    def _consent_page_response(
        referee: TutorReferee, tutor_name: str
    ) -> RefereeConsentPageResponse:
        return RefereeConsentPageResponse(
            referee_name=referee.full_name,
            referee_email=referee.email,
            tutor_name=tutor_name,
            status=referee.status,
            token_expires_at=referee.token_expires_at,
        )

    async def submit_consent(
        self,
        token: str,
        payload: RefereeConsentSubmission,
        *,
        client_ip: str | None,
    ) -> RefereeConsentPageResponse:
        # The repository locks the invitation row so two simultaneous requests
        # cannot submit the same single-use link twice.
        referee = await self.repository.get_by_token_hash(self._token_hash(token))
        if referee is None:
            raise HTTPException(
                status_code=404,
                detail="This referee invitation is invalid or has already been used.",
            )

        now = datetime.now(timezone.utc)
        if referee.token_expires_at <= now:
            referee.status = RefereeStatus.EXPIRED
            referee.consent_token_hash = None
            await self.db.commit()
            raise HTTPException(
                status_code=410, detail="This referee invitation has expired."
            )

        if referee.status != RefereeStatus.PENDING:
            raise HTTPException(
                status_code=409,
                detail="This referee invitation has already been answered.",
            )

        form = payload.reference_form
        referee.consented_name = payload.consented_name
        referee.responded_at = now
        referee.reference_submitted_at = now
        referee.reference_ip_address = client_ip[:45] if client_ip else None
        referee.reference_response = form.model_dump(mode="json")
        referee.consent_statement = CONSENT_TEXT
        referee.consented_at = now
        referee.status = RefereeStatus.CONSENTED
        referee.safeguarding_review_required = form.requires_safeguarding_review
        referee.safeguarding_review_reasons = form.safeguarding_review_reasons

        if form.requires_safeguarding_review:
            verification = await self.verifications.get_by_tutor_for_update(
                referee.tutor_user_id
            )
            if verification is None:
                verification = TutorVerification(tutor_user_id=referee.tutor_user_id)
                self.db.add(verification)
                await self.db.flush()

            verification.safeguarding_review_required = True
            if verification.status == VerificationStatus.APPROVED:
                # A late adverse reference must suspend the previous approval
                # until an administrator completes a fresh review.
                verification.status = VerificationStatus.PENDING_REVIEW
                verification.reviewed_by = None
                verification.reviewed_at = None
                verification.review_notes = None
            existing_reasons = list(verification.safeguarding_review_reasons or [])
            for reason in form.safeguarding_review_reasons:
                if reason not in existing_reasons:
                    existing_reasons.append(reason)
            verification.safeguarding_review_reasons = existing_reasons
            # A new safeguarding response requires a fresh human review.
            verification.safeguarding_reviewed_by = None
            verification.safeguarding_reviewed_at = None
            verification.safeguarding_review_notes = None

        # Invalidate the token in the same transaction as the response and audit data.
        referee.consent_token_hash = None
        await self.db.commit()

        tutor = await self.db.get(User, referee.tutor_user_id)
        tutor_name = (
            f"{tutor.first_name} {tutor.last_name}".strip() if tutor else "Tutova tutor"
        )
        return self._consent_page_response(referee, tutor_name)
