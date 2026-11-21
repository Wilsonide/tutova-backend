"""Tutova's monthly tutor commission policy.

Rates are based on the date an administrator approves the tutor, not account
creation or the number of lessons or contracts completed.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

TUTOVA_TIMEZONE = timezone(timedelta(hours=1))


def add_calendar_months(value: date | datetime, months: int) -> date | datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _as_tutova_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        # SQLAlchemy timestamps are timezone-aware; treating an unexpected
        # naive timestamp as UTC avoids silently interpreting it as Nigeria time.
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TUTOVA_TIMEZONE)


def completed_tenure_months(approved_at: datetime, as_of: datetime | date) -> int:
    """Return completed calendar months since administrator approval."""
    approval_local = _as_tutova_datetime(approved_at)
    date_only = isinstance(as_of, date) and not isinstance(as_of, datetime)
    if date_only:
        current_date = as_of
        joined_date = approval_local.date()
        if current_date < joined_date:
            return 0
        months = (current_date.year - joined_date.year) * 12 + (
            current_date.month - joined_date.month
        )
        anniversary_date = add_calendar_months(joined_date, months)
        if current_date < anniversary_date:
            months -= 1
        return max(months, 0)

    current = _as_tutova_datetime(as_of)
    if current < approval_local:
        return 0
    months = (current.year - approval_local.year) * 12 + current.month - approval_local.month
    anniversary = add_calendar_months(approval_local, months)
    if current < anniversary:
        months -= 1
    return max(months, 0)


def commission_bps_for_tenure(completed_months: int | Decimal) -> int:
    """25% in month one; 20% after month one until month three; 15% from month three."""
    months = Decimal(str(completed_months))
    if months < 1:
        return 2500
    if months < 3:
        return 2000
    return 1500


def split_monthly_commission(gross_tutor_fee_minor: int, commission_bps: int) -> dict[str, int]:
    """Split total commission equally, assigning any odd kobo to learner share."""
    total = (gross_tutor_fee_minor * commission_bps + 5000) // 10000
    tutor_share = total // 2
    learner_share = total - tutor_share
    return {
        "platform_fee_minor": total,
        "tutor_commission_minor": tutor_share,
        "learner_fee_minor": learner_share,
        "tutor_earning_minor": gross_tutor_fee_minor - tutor_share,
        "learner_total_minor": gross_tutor_fee_minor + learner_share,
    }


def build_monthly_commission_schedule(
    *,
    monthly_fee_minor: int,
    duration_months: int,
    period_start: date,
    tutor_approved_at: datetime,
) -> list[dict[str, int | str]]:
    """Create an immutable commission snapshot for every contract month."""
    schedule: list[dict[str, int | str]] = []
    for offset in range(duration_months):
        month_index = period_start.month - 1 + offset
        year = period_start.year + month_index // 12
        month = month_index % 12 + 1
        calendar_month_start = date(year, month, 1)
        next_month_index = month_index + 1
        next_year = period_start.year + next_month_index // 12
        next_month = next_month_index % 12 + 1
        calendar_month_end = date(next_year, next_month, 1) - timedelta(days=1)
        month_start = max(period_start, calendar_month_start)
        month_end = calendar_month_end
        # Each calendar earning month uses the tenure tier reached by its
        # final day. The monthly schedule is persisted as an immutable snapshot.
        tenure_months = completed_tenure_months(tutor_approved_at, month_end)
        bps = commission_bps_for_tenure(tenure_months)
        split = split_monthly_commission(monthly_fee_minor, bps)
        schedule.append(
            {
                "period_start": month_start.isoformat(),
                "period_end": month_end.isoformat(),
                "tenure_months": tenure_months,
                "commission_bps": bps,
                "tutoring_amount_minor": monthly_fee_minor,
                **split,
            }
        )
    return schedule
