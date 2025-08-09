# app/api/v1/notifications.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.notification_service import notification_service

router = APIRouter()

@router.get("/")
async def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Get user notifications"""
    return notification_service.get_user_notifications(
        db, current_user.id, unread_only, limit
    )

@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Mark notification as read"""
    return notification_service.mark_notification_as_read(
        db, notification_id, current_user.id
    )
