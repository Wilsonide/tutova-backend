import uuid

from fastapi import APIRouter, Response, status

from app.core.dependencies import DBSession, RequireParent
from app.domain.learners.schemas.learner import (
    LearnerProfileCreate,
    LearnerProfileResponse,
    LearnerProfileUpdate,
)
from app.domain.parents.schemas.parent import ParentProfileResponse
from app.domain.parents.services.parent_service import ParentService

router = APIRouter(
    prefix="/parents",
    tags=["Parents"],
)


# =====================================================
# PARENT PROFILE
# =====================================================


@router.post(
    "/profile",
    response_model=ParentProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_parent_profile(
    current_user: RequireParent,
    db: DBSession,
):
    service = ParentService(db)

    profile = await service.create_profile(current_user)

    await db.commit()

    return profile


@router.get(
    "/profile",
    response_model=ParentProfileResponse,
)
async def get_parent_profile(
    current_user: RequireParent,
    db: DBSession,
):
    return await ParentService(db).get_profile(current_user)


# =====================================================
# CHILD LEARNER MANAGEMENT
# =====================================================


@router.post(
    "/learners",
    response_model=LearnerProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_learner(
    data: LearnerProfileCreate,
    current_user: RequireParent,
    db: DBSession,
):
    learner = await ParentService(db).add_learner(
        current_user,
        data,
    )

    await db.commit()

    return learner


@router.get(
    "/learners",
    response_model=list[LearnerProfileResponse],
)
async def list_learners(
    current_user: RequireParent,
    db: DBSession,
):
    return await ParentService(db).list_learners(current_user)


@router.get(
    "/learners/{learner_id}",
    response_model=LearnerProfileResponse,
)
async def get_learner(
    learner_id: uuid.UUID,
    current_user: RequireParent,
    db: DBSession,
):
    return await ParentService(db).get_learner(
        current_user,
        learner_id,
    )


@router.patch(
    "/learners/{learner_id}",
    response_model=LearnerProfileResponse,
)
async def update_learner(
    learner_id: uuid.UUID,
    data: LearnerProfileUpdate,
    current_user: RequireParent,
    db: DBSession,
):
    learner = await ParentService(db).update_learner(
        current_user,
        learner_id,
        data,
    )

    await db.commit()

    return learner


@router.delete(
    "/learners/{learner_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_learner(
    learner_id: uuid.UUID,
    current_user: RequireParent,
    db: DBSession,
):
    await ParentService(db).delete_learner(
        current_user,
        learner_id,
    )

    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
