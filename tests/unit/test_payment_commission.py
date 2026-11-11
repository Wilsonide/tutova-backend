from decimal import Decimal

from app.domain.payments.services.payment_service import PaymentService


def test_new_tutor_commission_is_25_percent():
    assert PaymentService._commission_bps(Decimal("0")) == 2500


def test_tutor_with_less_than_50_hours_commission_is_20_percent():
    assert PaymentService._commission_bps(Decimal("0.5")) == 2000
    assert PaymentService._commission_bps(Decimal("49.99")) == 2000


def test_exactly_50_hours_remains_at_20_percent():
    assert PaymentService._commission_bps(Decimal("50")) == 2000


def test_more_than_50_hours_commission_is_15_percent():
    assert PaymentService._commission_bps(Decimal("50.01")) == 1500
