from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.services import notification_service
from app.services.notification_service import NotificationList


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)


# Sempre os avisos do próprio usuário logado: não há como pedir os de outra pessoa.

@router.get("/", response_model=NotificationList)
def list_notifications(current=Depends(get_current_user)):
    return notification_service.list_for(current)


@router.post("/{notification_id}/read", response_model=NotificationList)
def mark_notification_read(notification_id: UUID, current=Depends(get_current_user)):
    notification_service.mark_read(notification_id, current)

    return notification_service.list_for(current)
