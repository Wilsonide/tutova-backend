import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.verification.models.tutor_referee import TutorReferee


class RefereeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_tutor(self, tutor_user_id: uuid.UUID) -> list[TutorReferee]:
        return list((await self.db.scalars(
            select(TutorReferee)
            .where(TutorReferee.tutor_user_id == tutor_user_id)
            .order_by(TutorReferee.created_at.asc())
        )).all())

    async def get_by_token_hash(self, token_hash: str) -> TutorReferee | None:
        return await self.db.scalar(
            select(TutorReferee)
            .where(TutorReferee.consent_token_hash == token_hash)
            .with_for_update()
        )

    async def save_many(self, referees: list[TutorReferee]) -> None:
        self.db.add_all(referees)
        await self.db.flush()
