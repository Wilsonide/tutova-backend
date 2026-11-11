from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.subjects.models.subject import Subject


class SubjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, subject_id):
        result = await self.db.execute(select(Subject).where(Subject.id == subject_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str):
        result = await self.db.execute(select(Subject).where(Subject.slug == slug))
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Subject]:
        result = await self.db.execute(
            select(Subject)
            .where(Subject.is_active.is_(True))
            .order_by(Subject.name.asc())
        )
        return list(result.scalars().all())

    async def create(self, subject: Subject) -> Subject:
        self.db.add(subject)
        await self.db.flush()
        await self.db.refresh(subject)
        return subject
