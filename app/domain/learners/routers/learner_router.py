from fastapi import APIRouter, status

from app.core.dependencies import DBSession, RequireAdultLearner
from app.domain.learners.schemas.learner import (
    LearnerProfileCreate,
    LearnerProfileResponse,
    LearnerProfileUpdate,
)
from app.domain.learners.services.learner_service import LearnerService

router = APIRouter(
    prefix="/learners",
    tags=["Learners"],
)


@router.post(
    "/profile",
    response_model=LearnerProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_learner_profile(
    data: LearnerProfileCreate,
    current_user: RequireAdultLearner,
    db: DBSession,
):
    learner = await LearnerService(db).create_profile(
        current_user,
        data,
    )
    await db.commit()
    return learner


@router.get(
    "/profile",
    response_model=LearnerProfileResponse,
)
async def get_learner_profile(
    current_user: RequireAdultLearner,
    db: DBSession,
):
    return await LearnerService(db).get_profile(current_user)


@router.patch(
    "/profile",
    response_model=LearnerProfileResponse,
)
async def update_learner_profile(
    data: LearnerProfileUpdate,
    current_user: RequireAdultLearner,
    db: DBSession,
):
    learner = await LearnerService(db).update_profile(
        current_user,
        data,
    )
    await db.commit()
    return learner
