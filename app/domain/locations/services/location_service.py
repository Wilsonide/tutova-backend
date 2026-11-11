import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.models.user import User, UserRole
from app.domain.locations.models.location import Location, LocationType
from app.domain.locations.repositories.location_repository import LocationRepository
from app.domain.locations.schemas.location import CommunityCreate, LocationCreate

ALLOWED_PARENT_TYPES = {
    LocationType.STATE: set(),
    LocationType.CITY: {LocationType.STATE},
    LocationType.LGA: {LocationType.STATE},
    LocationType.NEIGHBORHOOD: {
        LocationType.CITY,
        LocationType.LGA,
    },
}


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


class LocationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.locations = LocationRepository(db)

    async def list_active(
        self,
        location_type: LocationType | None = None,
        parent_id: uuid.UUID | None = None,
    ) -> list[Location]:
        return await self.locations.list_active(
            location_type=location_type,
            parent_id=parent_id,
        )

    async def create(self, user: User, data: LocationCreate) -> Location:
        if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access is required.",
            )

        slug = data.slug.strip().lower()

        if await self.locations.get_by_slug(slug):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A location with this slug already exists.",
            )

        if data.location_type == LocationType.STATE:
            if data.parent_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A state cannot have a parent location.",
                )
        else:
            if data.parent_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This location type requires a parent location.",
                )

            parent = await self.locations.get_by_id(data.parent_id)

            if not parent or not parent.is_active:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="The parent location does not exist or is inactive.",
                )

            allowed = ALLOWED_PARENT_TYPES[data.location_type]

            if parent.location_type not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid parent location type.",
                )

            if parent.country_code != data.country_code.upper():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Parent and child locations must use the same country.",
                )

        location = Location(
            name=data.name.strip(),
            slug=slug,
            location_type=data.location_type,
            parent_id=data.parent_id,
            country_code=data.country_code.upper(),
        )

        return await self.locations.create(location)

    async def create_or_get_community(
        self,
        user: User,
        data: CommunityCreate,
    ) -> Location:
        if user.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tutors can add communities through tutor onboarding.",
            )

        name = " ".join(data.name.strip().split())

        if len(name) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Enter a valid community name.",
            )

        lga = await self.locations.get_by_id(data.lga_id)

        if not lga or not lga.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The selected LGA could not be found.",
            )

        if lga.location_type != LocationType.LGA:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A community must belong to an LGA.",
            )

        community_slug = slugify(name)

        if not community_slug:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Enter a valid community name.",
            )

        # Parent prefix makes the slug unique across different LGAs.
        slug = f"{lga.slug}-community-{community_slug}"

        if len(slug) > 180:
            slug = slug[:180].rstrip("-")

        return await self.locations.create_or_get_by_slug(
            name=name,
            slug=slug,
            parent_id=lga.id,
            country_code=lga.country_code,
        )

    async def get_active_by_id(self, location_id: uuid.UUID) -> Location:
        location = await self.locations.get_by_id(location_id)

        if not location or not location.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Location not found.",
            )

        return location
