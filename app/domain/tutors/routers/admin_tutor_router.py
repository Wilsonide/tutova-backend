import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.core.dependencies import DBSession, RequireBookingAdmin
from app.domain.authentication.models.user import UserStatus
from app.domain.tutors.schemas.admin_tutor import (
    AdminTutorListResponse,
    AdminTutorResponse,
    AdminTutorStatusUpdate,
)
from app.domain.tutors.services.admin_tutor_service import AdminTutorService

router = APIRouter(
    prefix="/admin/tutors",
    tags=["Admin - Tutors"],
)


@router.get(
    "",
    response_model=AdminTutorListResponse,
)
async def list_tutors(
    db: DBSession,
    admin: RequireBookingAdmin,
    page: Annotated[int, Query(ge=1)] = 1,
    profile_completion: Annotated[
        Literal["complete", "incomplete"] | None,
        Query(),
    ] = None,
    verification_completion: Annotated[
        Literal["complete", "incomplete"] | None,
        Query(),
    ] = None,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=150)] = None,
    account_status: Annotated[
        UserStatus | None,
        Query(alias="status"),
    ] = None,
):
    return await AdminTutorService(db).list_tutors(
        page=page,
        per_page=per_page,
        search=search,
        account_status=account_status,
        profile_completion=profile_completion,
        verification_completion=verification_completion,
    )


@router.get(
    "/{user_id}",
    response_model=AdminTutorResponse,
)
async def get_tutor(
    user_id: uuid.UUID,
    db: DBSession,
    admin: RequireBookingAdmin,
):
    return await AdminTutorService(db).get_tutor(user_id)


@router.patch(
    "/{user_id}/status",
    response_model=AdminTutorResponse,
)
async def update_tutor_status(
    user_id: uuid.UUID,
    data: AdminTutorStatusUpdate,
    db: DBSession,
    admin: RequireBookingAdmin,
):
    result = await AdminTutorService(db).update_tutor_status(
        user_id=user_id,
        new_status=data.status,
    )

    await db.commit()

    return result
