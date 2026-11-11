import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.locations.models.location import Location


class LocationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, location_id: uuid.UUID) -> Location | None:
        result = await self.db.execute(
            select(Location).where(Location.id == location_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Location | None:
        result = await self.db.execute(select(Location).where(Location.slug == slug))
        return result.scalar_one_or_none()

    async def list_active(
        self,
        location_type=None,
        parent_id: uuid.UUID | None = None,
    ) -> list[Location]:
        query = select(Location).where(Location.is_active.is_(True))

        if location_type is not None:
            query = query.where(Location.location_type == location_type)

        query = query.where(Location.parent_id == parent_id)
        query = query.order_by(Location.name.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, location: Location) -> Location:
        self.db.add(location)
        await self.db.flush()
        await self.db.refresh(location)
        return location

    async def create_or_get_by_slug(
        self,
        *,
        name: str,
        slug: str,
        parent_id: uuid.UUID,
        country_code: str,
    ) -> Location:
        statement = (
            pg_insert(Location)
            .values(
                name=name,
                slug=slug,
                location_type="NEIGHBORHOOD",
                parent_id=parent_id,
                country_code=country_code,
                is_active=True,
            )
            .on_conflict_do_nothing(index_elements=["slug"])
            .returning(Location.id)
        )

        result = await self.db.execute(statement)
        location_id = result.scalar_one_or_none()

        if location_id is None:
            existing = await self.get_by_slug(slug)

            if existing is None:
                raise RuntimeError("The community could not be created or retrieved.")

            return existing

        location = await self.get_by_id(location_id)

        if location is None:
            raise RuntimeError("The newly created community could not be retrieved.")

        return location
