from datetime import date, datetime, timezone
from decimal import Decimal

from app.domain.payments.services.commission_policy import (
    build_monthly_commission_schedule,
    commission_bps_for_tenure,
    completed_tenure_months,
    split_monthly_commission,
)
from app.domain.payments.services.payment_service import PaymentService


def test_new_tutor_first_month_commission_is_20_percent():
    assert commission_bps_for_tenure(Decimal("0")) == 2000
    assert commission_bps_for_tenure(Decimal("0.99")) == 2000


def test_relatively_new_tutor_after_first_month_and_before_three_months_is_15_percent():
    assert commission_bps_for_tenure(Decimal("1")) == 1500
    assert commission_bps_for_tenure(Decimal("2.99")) == 1500


def test_returning_tutor_from_three_months_is_10_percent():
    assert commission_bps_for_tenure(Decimal("3")) == 1000
    assert commission_bps_for_tenure(Decimal("4")) == 1000


def test_payment_service_uses_the_same_tenure_policy():
    assert PaymentService._commission_bps(Decimal("0")) == 2000
    assert PaymentService._commission_bps(Decimal("1")) == 1500
    assert PaymentService._commission_bps(Decimal("3")) == 1000


def test_tenure_uses_calendar_anniversaries_and_clamps_month_end():
    approved = datetime(2026, 1, 31, 10, 0, tzinfo=timezone.utc)
    assert completed_tenure_months(approved, date(2026, 2, 27)) == 0
    assert completed_tenure_months(approved, date(2026, 2, 28)) == 1
    assert completed_tenure_months(approved, date(2026, 4, 30)) == 3


def test_parent_always_pays_five_percent_and_tutor_covers_the_remainder():
    gross = 1_000_000  # ₦10,000 in kobo

    new_tutor = split_monthly_commission(gross, 2000)
    assert new_tutor["platform_fee_minor"] == 200_000
    assert new_tutor["learner_fee_minor"] == 50_000
    assert new_tutor["tutor_commission_minor"] == 150_000
    assert new_tutor["tutor_earning_minor"] == 850_000
    assert new_tutor["learner_total_minor"] == 1_050_000

    relatively_new = split_monthly_commission(gross, 1500)
    assert relatively_new["platform_fee_minor"] == 150_000
    assert relatively_new["learner_fee_minor"] == 50_000
    assert relatively_new["tutor_commission_minor"] == 100_000
    assert relatively_new["tutor_earning_minor"] == 900_000
    assert relatively_new["learner_total_minor"] == 1_050_000

    returning = split_monthly_commission(gross, 1000)
    assert returning["platform_fee_minor"] == 100_000
    assert returning["learner_fee_minor"] == 50_000
    assert returning["tutor_commission_minor"] == 50_000
    assert returning["tutor_earning_minor"] == 950_000
    assert returning["learner_total_minor"] == 1_050_000


def test_monthly_schedule_changes_rate_as_tutor_tenure_changes():
    approved = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    schedule = build_monthly_commission_schedule(
        monthly_fee_minor=1_000_000,
        duration_months=4,
        period_start=date(2026, 1, 15),
        tutor_approved_at=approved,
    )

    assert [item["commission_bps"] for item in schedule] == [
        2000, 1500, 1500, 1000
    ]
    assert [item["parent_fee_bps"] for item in schedule] == [500, 500, 500, 500]
    assert [item["tutor_commission_minor"] for item in schedule] == [
        150_000, 100_000, 100_000, 50_000
    ]
    assert [item["learner_fee_minor"] for item in schedule] == [
        50_000, 50_000, 50_000, 50_000
    ]


def test_approval_date_is_the_start_of_commission_tenure():
    approved = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    assert completed_tenure_months(approved, date(2026, 1, 14)) == 0
    assert commission_bps_for_tenure(completed_tenure_months(approved, date(2026, 2, 14))) == 2000
    assert commission_bps_for_tenure(completed_tenure_months(approved, date(2026, 2, 15))) == 1500
    assert commission_bps_for_tenure(completed_tenure_months(approved, date(2026, 4, 14))) == 1500
    assert commission_bps_for_tenure(completed_tenure_months(approved, date(2026, 4, 15))) == 1000


def test_rounding_preserves_parent_five_percent_and_total_commission():
    split = split_monthly_commission(101, 2000)
    assert split["platform_fee_minor"] == 20
    assert split["learner_fee_minor"] == 5
    assert split["tutor_commission_minor"] == 15
    assert split["tutor_commission_minor"] + split["learner_fee_minor"] == split["platform_fee_minor"]
