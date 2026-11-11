import uuid

from fastapi import APIRouter, status

from app.core.dependencies import (
    DBSession,
    RequireBookingAdmin,
    RequireTutor,
)
from app.domain.locations.models.location import LocationType
from app.domain.locations.schemas.location import (
    CommunityCreate,
    LocationCreate,
    LocationResponse,
)
from app.domain.locations.services.location_service import LocationService

router = APIRouter(
    prefix="/locations",
    tags=["Locations"],
)


@router.get(
    "",
    response_model=list[LocationResponse],
)
async def list_locations(
    db: DBSession,
    location_type: LocationType | None = None,
    parent_id: uuid.UUID | None = None,
):
    return await LocationService(db).list_active(
        location_type=location_type,
        parent_id=parent_id,
    )


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_location(
    data: LocationCreate,
    current_user: RequireBookingAdmin,
    db: DBSession,
):
    location = await LocationService(db).create(current_user, data)
    await db.commit()
    return location


@router.post(
    "/communities",
    response_model=LocationResponse,
    status_code=status.HTTP_200_OK,
)
async def create_or_get_community(
    data: CommunityCreate,
    current_user: RequireTutor,
    db: DBSession,
):
    location = await LocationService(db).create_or_get_community(
        current_user,
        data,
    )
    await db.commit()
    return location


@router.get(
    "/{location_id}",
    response_model=LocationResponse,
)
async def get_location(
    location_id: uuid.UUID,
    db: DBSession,
):
    return await LocationService(db).get_active_by_id(location_id)
