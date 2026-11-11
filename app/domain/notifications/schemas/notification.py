import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.notifications.models.notification import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_type: NotificationType
    title: str
    message: str
    data: dict | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int
    total: int
    limit: int
    offset: int


class NotificationReadResponse(BaseModel):
    id: uuid.UUID
    read_at: datetime
    message: str
