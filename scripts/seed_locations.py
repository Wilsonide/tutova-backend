import asyncio
import re

from sqlalchemy import insert, select

import app.db.model_registry  # noqa: F401
from app.core.database import AsyncSessionFactory, engine
from app.domain.locations.models.location import Location, LocationType

NIGERIAN_STATES = [
    "Abia",
    "Adamawa",
    "Akwa Ibom",
    "Anambra",
    "Bauchi",
    "Bayelsa",
    "Benue",
    "Borno",
    "Cross River",
    "Delta",
    "Ebonyi",
    "Edo",
    "Ekiti",
    "Enugu",
    "Gombe",
    "Imo",
    "Jigawa",
    "Kaduna",
    "Kano",
    "Katsina",
    "Kebbi",
    "Kogi",
    "Kwara",
    "Lagos",
    "Nasarawa",
    "Niger",
    "Ogun",
    "Ondo",
    "Osun",
    "Oyo",
    "Plateau",
    "Rivers",
    "Sokoto",
    "Taraba",
    "Yobe",
    "Zamfara",
    "Federal Capital Territory",
]


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


async def main():
    locations_table = Location.__table__

    records = [
        {
            "name": name,
            "slug": slugify(name),
            "location_type": LocationType.STATE,
            "parent_id": None,
            "country_code": "NG",
            "is_active": True,
        }
        for name in NIGERIAN_STATES
    ]

    slugs = [record["slug"] for record in records]

    try:
        async with AsyncSessionFactory() as db:
            result = await db.execute(
                select(locations_table.c.slug).where(locations_table.c.slug.in_(slugs))
            )

            existing_slugs = set(result.scalars().all())

            new_records = [
                record for record in records if record["slug"] not in existing_slugs
            ]

            if new_records:
                await db.execute(
                    insert(locations_table),
                    new_records,
                )
                await db.commit()
            else:
                print("All Nigerian states already exist.")

            print("\nLocation seeding completed.")
            print(f"Total states and FCT: {len(records)}")
            print(f"New locations added: {len(new_records)}")
            print(f"Existing locations skipped: {len(existing_slugs)}")

            if new_records:
                print("\nAdded locations:")
                for record in new_records:
                    print(f"  - {record['name']}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
