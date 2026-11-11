"""Regression checks for the replacement booking payment lifecycle."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_payment_module_uses_existing_lesson_booking_domain():
    source = (ROOT / "app/domain/payments/services/payment_service.py").read_text()
    assert "from app.domain.session_bookings.models.lesson_booking import" in source
    assert "from app.domain.learning_workflows.models" not in source


def test_successful_payment_is_verified_against_provider_amount_and_currency():
    source = (ROOT / "app/domain/payments/services/payment_service.py").read_text()
    assert "provider.verify_payment(provider_reference=reference)" in source
    assert "verified.amount_minor != payment.amount_minor" in source
    assert "verified.currency.upper() != payment.currency.upper()" in source


def test_platform_and_tutor_shares_are_snapshotted_on_payment():
    source = (ROOT / "app/domain/payments/services/payment_service.py").read_text()
    assert "commission_bps=commission_bps" in source
    assert "platform_fee_minor=platform_fee" in source
    assert "tutor_earning_minor=tutor_earning" in source
