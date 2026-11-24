import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.progress_logs.models.progress_log_entry import (
    ProgressLogEntry,
    ProgressLogReviewStatus,
)


class ProgressLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, entry: ProgressLogEntry) -> ProgressLogEntry:
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_by_id_with_author(self, entry_id: uuid.UUID) -> ProgressLogEntry:
        result = await self.db.execute(
            select(ProgressLogEntry)
            .options(selectinload(ProgressLogEntry.author))
            .where(ProgressLogEntry.id == entry_id)
        )
        return result.scalar_one()

    async def list_for_request(self, request_id: uuid.UUID) -> list[ProgressLogEntry]:
        result = await self.db.scalars(
            select(ProgressLogEntry)
            .options(selectinload(ProgressLogEntry.author))
            .where(ProgressLogEntry.tutoring_request_id == request_id)
            .order_by(ProgressLogEntry.created_at.asc())
        )
        return list(result.all())

    async def list_admin(
        self,
        status_filter: ProgressLogReviewStatus | None = None,
        limit: int = 200,
    ) -> list[ProgressLogEntry]:
        query = (
            select(ProgressLogEntry)
            .options(
                selectinload(ProgressLogEntry.author),
                selectinload(ProgressLogEntry.tutoring_request),
            )
            .order_by(ProgressLogEntry.created_at.desc())
            .limit(limit)
        )
        if status_filter is not None:
            query = query.where(ProgressLogEntry.review_status == status_filter)
        result = await self.db.scalars(query)
        return list(result.all())

    async def get_for_update(self, entry_id: uuid.UUID) -> ProgressLogEntry | None:
        result = await self.db.execute(
            select(ProgressLogEntry)
            .where(ProgressLogEntry.id == entry_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()
