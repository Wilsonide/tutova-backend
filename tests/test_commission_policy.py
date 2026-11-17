from decimal import Decimal

from app.domain.payments.services.payment_service import PaymentService


def test_new_tutor_commission_is_25_percent():
    assert PaymentService._commission_bps(Decimal("0")) == 2500


def test_less_than_three_completed_months_commission_is_20_percent():
    assert PaymentService._commission_bps(Decimal("2.99")) == 2000


def test_exactly_three_completed_months_commission_is_15_percent():
    assert PaymentService._commission_bps(Decimal("3")) == 1500


def test_more_than_three_completed_months_commission_is_15_percent():
    assert PaymentService._commission_bps(Decimal("4")) == 1500


def test_commission_is_deducted_from_learner_payment():
    gross = 10_000_00  # ₦10,000 in kobo
    commission_bps = PaymentService._commission_bps(Decimal("0"))
    platform_fee = (gross * commission_bps + 5000) // 10000
    tutor_earning = gross - platform_fee

    assert platform_fee == 250_000
    assert tutor_earning == 750_000
    assert platform_fee + tutor_earning == gross
