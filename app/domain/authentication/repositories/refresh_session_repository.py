import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.models.refresh_session import RefreshSession


class RefreshSessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, session: RefreshSession) -> RefreshSession:
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_valid_session(
        self,
        token_hash: str,
    ) -> RefreshSession | None:
        now = datetime.now(UTC)

        result = await self.db.execute(
            select(RefreshSession).where(
                RefreshSession.token_hash == token_hash,
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, session: RefreshSession) -> None:
        session.revoked_at = datetime.now(UTC)
        await self.db.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(RefreshSession).where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
            )
        )

        for session in result.scalars().all():
            session.revoked_at = datetime.now(UTC)

        await self.db.flush()
