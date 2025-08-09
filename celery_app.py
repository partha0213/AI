# app/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "ai_intern_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_reject_on_worker_lost=True,
)

# app/tasks.py
from .celery_app import celery_app
from app.services.notification_service import notification_service
from app.services.ai_service import ai_service

@celery_app.task
def send_welcome_email_task(user_id: int, email: str, name: str):
    """Background task to send welcome email"""
    asyncio.run(send_welcome_email(email, name))

@celery_app.task
def process_ai_assessment_task(intern_id: int, assessment_data: dict):
    """Background task for AI assessment processing"""
    result = asyncio.run(ai_service.assess_skills_ai(assessment_data))
    # Update database with results
    return result

@celery_app.task
def cleanup_expired_notifications_task():
    """Daily cleanup task for expired notifications"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        count = notification_service.clean_expired_notifications(db)
        return f"Cleaned up {count} expired notifications"
    finally:
        db.close()
