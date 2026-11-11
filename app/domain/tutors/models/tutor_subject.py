from sqlalchemy import Column, ForeignKey, Table

from app.db.base import Base

tutor_subjects = Table(
    "tutor_subjects",
    Base.metadata,
    Column(
        "tutor_id",
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "subject_id",
        ForeignKey("subjects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
