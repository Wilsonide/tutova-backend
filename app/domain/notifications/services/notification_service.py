import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notifications.models.notification import (
    Notification,
    NotificationType,
)
from app.domain.notifications.repositories.notification_repository import (
    NotificationRepository,
)


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = NotificationRepository(db)

    async def create(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        data: dict | None = None,
    ) -> Notification:
        """
        Add a notification to the current database transaction.

        This method intentionally does not commit. The calling
        business operation owns the transaction.

        Used by booking operations to notify:
        - Tutors when learners request lesson bookings.
        - Learners when tutors accept booking requests.
        - Learners when tutors decline booking requests.
        - Existing session completion and acknowledgement events.
        """
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            data=data,
        )

        return await self.repository.create(notification)

    async def list_notifications(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """Return paginated notifications and unread count for a user."""
        items = await self.repository.list_for_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

        total, unread_count = await self.repository.count_summary_for_user(user_id)

        return {
            "items": items,
            "unread_count": unread_count,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def mark_read(
        self,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> Notification:
        """
        Mark one notification as read.

        The notification must belong to the requesting user.
        """
        notification = await self.repository.get_for_user(
            notification_id=notification_id,
            user_id=user_id,
            for_update=True,
        )

        if notification is None:
            raise HTTPException(
                status_code=404,
                detail="Notification not found.",
            )

        if notification.read_at is None:
            notification.read_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(notification)

        return notification

    async def mark_all_read(
        self,
        user_id: uuid.UUID,
    ) -> dict:
        """Mark all unread notifications belonging to a user as read."""
        read_at = await self.repository.mark_all_read(user_id)

        await self.db.commit()

        return {
            "read_at": read_at,
            "message": "All notifications have been marked as read.",
        }
