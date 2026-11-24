import uuid

from fastapi import APIRouter, Query, status

from app.core.dependencies import CurrentUser, DBSession
from app.domain.notifications.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
)
from app.domain.notifications.services.notification_service import (
    NotificationService,
)

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


@router.get(
    "",
    response_model=NotificationListResponse,
)
async def list_notifications(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    service = NotificationService(db)

    return await service.list_notifications(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = NotificationService(db)

    result = await service.mark_read(
        user_id=current_user.id,
        notification_id=notification_id,
    )

    return result


@router.patch(
    "/read-all",
    status_code=status.HTTP_200_OK,
)
async def mark_all_notifications_read(
    current_user: CurrentUser,
    db: DBSession,
):
    service = NotificationService(db)

    result = await service.mark_all_read(
        user_id=current_user.id,
    )

    return result
