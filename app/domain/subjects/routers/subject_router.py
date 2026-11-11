from fastapi import APIRouter, status

from app.core.dependencies import DBSession, RequireBookingAdmin
from app.domain.subjects.schemas.subject import (
    SubjectCreate,
    SubjectResponse,
)
from app.domain.subjects.services.subject_service import SubjectService

router = APIRouter(
    prefix="/subjects",
    tags=["Subjects"],
)


# =====================================================
# LIST ACTIVE SUBJECTS - PUBLIC
# =====================================================


@router.get(
    "",
    response_model=list[SubjectResponse],
)
async def list_subjects(
    db: DBSession,
):
    return await SubjectService(db).list_active()


# =====================================================
# CREATE SUBJECT - ADMIN ONLY
# =====================================================


@router.post(
    "",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subject(
    data: SubjectCreate,
    current_user: RequireBookingAdmin,
    db: DBSession,
):
    subject = await SubjectService(db).create(
        current_user,
        data,
    )

    await db.commit()

    return subject
