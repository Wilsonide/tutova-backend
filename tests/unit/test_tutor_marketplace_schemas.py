import pytest
from pydantic import ValidationError

from app.domain.tutors.schemas.tutor import (
    AvailabilityCreate,
    OfferingCreate,
    PricingCreate,
    ProfileUpsert,
)


def test_accepts_coding_and_professional_offerings():
    coding = OfferingCreate(
        category="CODING",
        title="Python for Beginners",
        description="Learn Python fundamentals and build small projects.",
    )
    professional = OfferingCreate(
        category="PROFESSIONAL",
        title="Project Management",
        description="Practical project planning and delivery skills.",
    )
    assert coding.category == "CODING"
    assert professional.category == "PROFESSIONAL"


def test_availability_requires_positive_time_window():
    with pytest.raises(ValidationError):
        AvailabilityCreate(day_of_week=1, start_time="16:00", end_time="09:00")


def test_contract_pricing_requires_scope():
    with pytest.raises(ValidationError):
        PricingCreate(pricing_model="CONTRACT", amount_minor=500000)


def test_hourly_pricing_rejects_contract_scope():
    with pytest.raises(ValidationError):
        PricingCreate(
            pricing_model="HOURLY",
            amount_minor=500000,
            contract_scope="Build a website",
        )


def test_profile_can_choose_multiple_work_modes_and_payout_preference():
    profile = ProfileUpsert(
        headline="Python and maths tutor",
        bio="I teach learners through structured lessons and practical projects.",
        years_experience=3,
        work_modes=["ONLINE", "IN_PERSON"],
        payout_method_preference="BANK_TRANSFER",
    )
    assert profile.work_modes == ["ONLINE", "IN_PERSON"]
    assert profile.payout_method_preference == "BANK_TRANSFER"
