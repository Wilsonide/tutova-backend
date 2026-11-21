from datetime import date, datetime, timezone
from decimal import Decimal

from app.domain.payments.services.commission_policy import (
    build_monthly_commission_schedule,
    commission_bps_for_tenure,
    completed_tenure_months,
    split_monthly_commission,
)
from app.domain.payments.services.payment_service import PaymentService


def test_new_tutor_first_month_commission_is_25_percent():
    assert commission_bps_for_tenure(Decimal("0")) == 2500
    assert commission_bps_for_tenure(Decimal("0.99")) == 2500


def test_tutor_after_first_month_and_before_three_months_is_20_percent():
    assert commission_bps_for_tenure(Decimal("1")) == 2000
    assert commission_bps_for_tenure(Decimal("2.99")) == 2000


def test_exactly_three_months_and_above_is_15_percent():
    assert commission_bps_for_tenure(Decimal("3")) == 1500
    assert commission_bps_for_tenure(Decimal("4")) == 1500


def test_payment_service_uses_the_same_tenure_policy():
    assert PaymentService._commission_bps(Decimal("0")) == 2500
    assert PaymentService._commission_bps(Decimal("1")) == 2000
    assert PaymentService._commission_bps(Decimal("3")) == 1500


def test_tenure_uses_calendar_anniversaries_and_clamps_month_end():
    approved = datetime(2026, 1, 31, 10, 0, tzinfo=timezone.utc)
    assert completed_tenure_months(approved, date(2026, 2, 27)) == 0
    assert completed_tenure_months(approved, date(2026, 2, 28)) == 1
    assert completed_tenure_months(approved, date(2026, 4, 30)) == 3


def test_commission_is_split_between_tutor_and_learner():
    gross = 1_000_000  # ₦10,000 in kobo
    split = split_monthly_commission(gross, 2500)

    assert split["platform_fee_minor"] == 250_000
    assert split["tutor_commission_minor"] == 125_000
    assert split["learner_fee_minor"] == 125_000
    assert split["tutor_earning_minor"] == 875_000
    assert split["learner_total_minor"] == 1_125_000
    assert (
        split["tutor_commission_minor"] + split["learner_fee_minor"]
        == split["platform_fee_minor"]
    )


def test_monthly_schedule_changes_rate_as_tutor_tenure_changes():
    approved = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    schedule = build_monthly_commission_schedule(
        monthly_fee_minor=1_000_000,
        duration_months=4,
        period_start=date(2026, 1, 15),
        tutor_approved_at=approved,
    )

    assert [item["commission_bps"] for item in schedule] == [
        2500, 2000, 2000, 1500
    ]
    assert [item["tutor_commission_minor"] for item in schedule] == [
        125_000, 100_000, 100_000, 75_000
    ]
    assert [item["learner_fee_minor"] for item in schedule] == [
        125_000, 100_000, 100_000, 75_000
    ]


def test_approval_date_is_the_start_of_commission_tenure():
    approved = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    assert completed_tenure_months(approved, date(2026, 1, 14)) == 0
    assert commission_bps_for_tenure(completed_tenure_months(approved, date(2026, 2, 14))) == 2500
    assert commission_bps_for_tenure(completed_tenure_months(approved, date(2026, 2, 15))) == 2000
    assert commission_bps_for_tenure(completed_tenure_months(approved, date(2026, 4, 14))) == 2000
    assert commission_bps_for_tenure(completed_tenure_months(approved, date(2026, 4, 15))) == 1500


def test_odd_kobo_is_assigned_to_learner_half():
    split = split_monthly_commission(101, 2500)
    assert split["platform_fee_minor"] == 25
    assert split["tutor_commission_minor"] == 12
    assert split["learner_fee_minor"] == 13
