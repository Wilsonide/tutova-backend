import asyncio
import json
import re
from pathlib import Path

from sqlalchemy import insert, select

import app.db.model_registry  # noqa: F401
from app.core.database import AsyncSessionFactory, engine
from app.domain.locations.models.location import Location

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "nigeria_lgas.json"

EXPECTED_LGA_COUNT = 774


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def load_lgas():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_FILE}\n"
            "Download all-lga.json and save it as data/nigeria_lgas.json."
        )

    with DATA_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError("The LGA dataset must contain a JSON array.")

    if len(records) != EXPECTED_LGA_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_LGA_COUNT} LGAs, but found {len(records)}."
        )

    return records


async def main():
    locations_table = Location.__table__

    try:
        print("Loading Nigerian LGA dataset...")

        source_records = load_lgas()

        async with AsyncSessionFactory() as db:
            result = await db.execute(
                select(
                    locations_table.c.id,
                    locations_table.c.name,
                    locations_table.c.slug,
                ).where(
                    locations_table.c.location_type == "STATE",
                    locations_table.c.country_code == "NG",
                )
            )

            state_rows = result.mappings().all()

            state_lookup = {slugify(state["name"]): state["id"] for state in state_rows}

            if len(state_lookup) != 37:
                raise ValueError(
                    "Expected 37 state/FCT records in your database. "
                    f"Found {len(state_lookup)}. "
                    "Run the state seeder first."
                )

            prepared_records = []

            for record in source_records:
                name = record.get("name", {}).get("en")
                parent_name = record.get("parent", {}).get("name", {}).get("en")

                if not name or not parent_name:
                    raise ValueError(f"Invalid LGA dataset record: {record}")

                parent_slug = slugify(parent_name)

                if parent_slug not in state_lookup:
                    raise ValueError(
                        f"Parent state not found: {parent_name} (LGA: {name})"
                    )

                prepared_records.append(
                    {
                        "name": name,
                        "slug": f"{parent_slug}-{slugify(name)}",
                        "location_type": "LGA",
                        "parent_id": state_lookup[parent_slug],
                        "country_code": "NG",
                        "is_active": True,
                    }
                )

            if len(prepared_records) != EXPECTED_LGA_COUNT:
                raise ValueError("Prepared LGA count does not match expected count.")

            slugs = [record["slug"] for record in prepared_records]

            if len(slugs) != len(set(slugs)):
                raise ValueError("Duplicate LGA slugs detected in the dataset.")

            result = await db.execute(
                select(locations_table.c.slug).where(
                    locations_table.c.location_type == "LGA",
                    locations_table.c.country_code == "NG",
                )
            )

            existing_slugs = set(result.scalars().all())

            new_records = [
                record
                for record in prepared_records
                if record["slug"] not in existing_slugs
            ]

            if new_records:
                await db.execute(
                    insert(locations_table),
                    new_records,
                )
                await db.commit()

            print("\nLGA seeding completed successfully.")
            print(f"Total LGAs in dataset: {len(prepared_records)}")
            print(f"New LGAs inserted: {len(new_records)}")
            print(f"Existing LGAs skipped: {len(existing_slugs)}")

    except Exception:
        raise

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
