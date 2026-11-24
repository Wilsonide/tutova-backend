import uuid
from datetime import datetime, timezone

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notifications.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        notification: Notification,
    ) -> Notification:
        self.db.add(notification)
        await self.db.flush()
        return notification

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Notification]:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_summary_for_user(
        self,
        user_id: uuid.UUID,
    ) -> tuple[int, int]:
        """Fetch total and unread counts with one aggregate query."""
        result = await self.db.execute(
            select(
                func.count(Notification.id),
                func.coalesce(
                    func.sum(case((Notification.read_at.is_(None), 1), else_=0)),
                    0,
                ),
            ).where(Notification.user_id == user_id)
        )
        total, unread = result.one()
        return int(total), int(unread)

    async def get_for_user(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
        for_update: bool = False,
    ) -> Notification | None:
        query = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )

        if for_update:
            query = query.with_for_update()

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def mark_all_read(
        self,
        user_id: uuid.UUID,
    ) -> datetime:
        now = datetime.now(timezone.utc)

        await self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=now)
        )

        return now
