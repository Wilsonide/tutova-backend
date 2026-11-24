"""Transactional email helpers used by background tasks.

Email delivery is deliberately kept outside database transactions. The
calling service schedules these synchronous functions with FastAPI
BackgroundTasks only after the relevant database commit succeeds.
"""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)
LAGOS_TZ = timezone(timedelta(hours=1), name="WAT")


def _send_email(recipient: str, subject: str, body: str) -> None:
    if not recipient or not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        logger.warning("Tutova transactional email skipped: SMTP is not configured.")
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = recipient
    message.set_content(body)

    try:
        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=10,
        ) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception:
        # Email failures must not roll back a completed booking/request action.
        logger.exception("Unable to deliver Tutova transactional email.")


def _format_lagos_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LAGOS_TZ).strftime("%A, %d %B %Y at %I:%M %p WAT")


def _frontend_url(path: str) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def send_booking_created_to_tutor(
    recipient: str,
    learner_name: str,
    booking_id: str,
    start_at: datetime,
    duration_minutes: int,
) -> None:
    _send_email(
        recipient,
        "A learner has booked a lesson on Tutova",
        (
            f"Hello,\n\n{learner_name} has completed payment and submitted a "
            "lesson booking for your review.\n\n"
            f"Requested lesson: {_format_lagos_time(start_at)}\n"
            f"Duration: {duration_minutes} minutes\n"
            f"Booking reference: {booking_id}\n\n"
            f"Sign in to review this booking: {_frontend_url('/lessons')}\n\n"
            "Please review the request and accept or decline it from your Tutova "
            "workspace.\n\nThe Tutova Team"
        ),
    )


def send_booking_confirmation_to_learner(
    recipient: str,
    tutor_name: str,
    booking_id: str,
    start_at: datetime,
    duration_minutes: int,
) -> None:
    _send_email(
        recipient,
        "Your Tutova booking request has been submitted",
        (
            f"Hello,\n\nYour payment has been verified and your booking request "
            f"has been sent to {tutor_name}. The tutor still needs to review and "
            "respond to the booking.\n\n"
            f"Requested lesson: {_format_lagos_time(start_at)}\n"
            f"Duration: {duration_minutes} minutes\n"
            f"Booking reference: {booking_id}\n\n"
            f"Track the booking in your Tutova workspace: {_frontend_url('/lessons')}\n\n"
            "The Tutova Team"
        ),
    )


def send_tutor_request_response_to_learner(
    recipient: str,
    tutor_name: str,
    decision: str,
    request_id: str,
    message: str,
) -> None:
    accepted = decision == "ACCEPT"
    subject = (
        "A tutor is interested in your Tutova request"
        if accepted
        else "An update about your selected Tutova tutor"
    )
    _send_email(
        recipient,
        subject,
        (
            f"Hello,\n\n{tutor_name} "
            f"{'has responded positively to' if accepted else 'is unable to accept'} "
            f"your tutoring request.\n\n{message}\n\n"
            f"Request reference: {request_id}\n"
            f"Review the update in your Tutova workspace: {_frontend_url('/requests')}\n\n"
            "The Tutova Team"
        ),
    )


def send_tutor_booking_response_to_learner(
    recipient: str,
    tutor_name: str,
    decision: str,
    booking_id: str,
    start_at: datetime,
) -> None:
    accepted = decision == "ACCEPT"
    _send_email(
        recipient,
        (
            "Your tutor accepted your Tutova booking"
            if accepted
            else "Your tutor declined your Tutova booking"
        ),
        (
            f"Hello,\n\n{tutor_name} "
            f"{'has accepted' if accepted else 'has declined'} your lesson booking.\n\n"
            f"Requested lesson: {_format_lagos_time(start_at)}\n"
            f"Booking reference: {booking_id}\n\n"
            f"View the booking in your Tutova workspace: {_frontend_url('/lessons')}\n\n"
            "The Tutova Team"
        ),
    )
