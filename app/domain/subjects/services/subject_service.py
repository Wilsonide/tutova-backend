from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.models.user import User, UserRole
from app.domain.subjects.models.subject import Subject
from app.domain.subjects.repositories.subject_repository import SubjectRepository
from app.domain.subjects.schemas.subject import SubjectCreate


class SubjectService:
    def __init__(self, db: AsyncSession):
        self.subjects = SubjectRepository(db)

    async def list_active(self) -> list[Subject]:
        return await self.subjects.list_active()

    async def create(self, user: User, data: SubjectCreate) -> Subject:
        if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access is required.",
            )

        name = data.name.strip()
        slug = data.slug.strip().lower()

        if await self.subjects.get_by_slug(slug):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A subject with this slug already exists.",
            )

        subject = Subject(
            name=name,
            slug=slug,
            description=data.description.strip() if data.description else None,
        )
        return await self.subjects.create(subject)
