from sqlalchemy import Column, ForeignKey, Table

from app.db.base import Base

tutor_locations = Table(
    "tutor_locations",
    Base.metadata,
    Column(
        "tutor_id",
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "location_id",
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
