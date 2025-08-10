import asyncio
import logging
from typing import Dict, Any, List
from celery import Celery
from datetime import datetime, timedelta
import json

from app.core.config import settings
from app.core.database import SessionLocal

# Configure Celery
celery_app = Celery(
    "ai_intern_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.tasks.background_tasks']
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_routes={
        'app.tasks.background_tasks.process_ai_assessment': {'queue': 'ai_queue'},
        'app.tasks.background_tasks.process_resume_analysis': {'queue': 'ai_queue'},
        'app.tasks.background_tasks.auto_grade_submission': {'queue': 'ai_queue'},
        'app.tasks.background_tasks.send_notification_email': {'queue': 'email_queue'},
        'app.tasks.background_tasks.generate_reports': {'queue': 'reports_queue'},
    }
)

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_resume_analysis(self, intern_id: int, file_content: bytes, filename: str):
    """Process resume analysis in background"""
    
    try:
        # Setup async environment
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Import AI service
            from app.services.ai_service import ai_service
            
            # Process resume
            result = loop.run_until_complete(
                ai_service.analyze_resume_ai(file_content, filename)
            )
            
            # Update database with results
            db = SessionLocal()
            try:
                from app.services.intern_service import update_intern_analysis
                update_intern_analysis(db, intern_id, result)
                
                # Send notification to intern
                send_analysis_complete_notification.delay(intern_id, result)
                
                logger.info(f"Resume analysis completed for intern {intern_id}")
                return {"status": "completed", "intern_id": intern_id, "result": result}
                
            finally:
                db.close()
                
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Resume analysis failed for intern {intern_id}: {str(exc)}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying resume analysis for intern {intern_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=exc)
        
        # Final failure - notify admin
        send_admin_alert.delay(
            f"Resume analysis failed for intern {intern_id}",
            f"Error: {str(exc)}"
        )
        
        return {"status": "failed", "intern_id": intern_id, "error": str(exc)}

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_ai_assessment(self, intern_id: int, assessment_data: Dict[str, Any]):
    """Process AI skills assessment in background"""
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.services.ai_service import ai_service
            
            # Process assessment
            result = loop.run_until_complete(
                ai_service.assess_skills_ai(assessment_data)
            )
            
            # Update database
            db = SessionLocal()
            try:
                from app.services.intern_service import update_intern_skills_assessment
                update_intern_skills_assessment(db, intern_id, result)
                
                # Generate personalized learning path
                generate_learning_path.delay(intern_id, result)
                
                logger.info(f"AI assessment completed for intern {intern_id}")
                return {"status": "completed", "intern_id": intern_id, "result": result}
                
            finally:
                db.close()
                
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"AI assessment failed for intern {intern_id}: {str(exc)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        
        return {"status": "failed", "intern_id": intern_id, "error": str(exc)}

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def auto_grade_submission(self, task_id: int, submission_data: Dict[str, Any]):
    """Auto-grade task submission in background"""
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.services.ai_service import ai_service
            from app.services.task_service import get_task_by_id, update_task_evaluation
            
            db = SessionLocal()
            try:
                # Get task and intern data
                task = get_task_by_id(db, task_id)
                if not task:
                    raise Exception(f"Task {task_id} not found")
                
                # Prepare data for AI evaluation
                task_data = {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "requirements": task.learning_objectives or []
                }
                
                intern_profile = {
                    "experience_level": task.assigned_intern.experience_level,
                    "skills": task.assigned_intern.skills or []
                }
                
                # Process evaluation
                result = loop.run_until_complete(
                    ai_service.auto_grade_submission(task_data, submission_data, intern_profile)
                )
                
                # Update task with evaluation
                update_task_evaluation(db, task_id, result)
                
                # Send feedback notification to intern
                send_evaluation_notification.delay(task.assigned_intern_id, task_id, result)
                
                logger.info(f"Auto-grading completed for task {task_id}")
                return {"status": "completed", "task_id": task_id, "result": result}
                
            finally:
                db.close()
                
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Auto-grading failed for task {task_id}: {str(exc)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        
        return {"status": "failed", "task_id": task_id, "error": str(exc)}

@celery_app.task
def send_notification_email(email: str, subject: str, body: str, html_body: str = None):
    """Send notification email"""
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.utils.email import send_email
            
            loop.run_until_complete(
                send_email([email], subject, body, html_body)
            )
            
            logger.info(f"Email sent successfully to {email}")
            return {"status": "sent", "email": email}
            
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Failed to send email to {email}: {str(exc)}")
        return {"status": "failed", "email": email, "error": str(exc)}

@celery_app.task
def generate_learning_path(intern_id: int, assessment_result: Dict[str, Any]):
    """Generate personalized learning path based on assessment"""
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.services.ai_service import ai_service
            from app.services.learning_service import create_personalized_learning_path
            
            # Generate learning path using AI
            intern_data = {
                "id": intern_id,
                "assessment": assessment_result,
                "skills": assessment_result.get("technical_skills", {}),
                "learning_style": assessment_result.get("learning_style", "visual")
            }
            
            learning_path = loop.run_until_complete(
                ai_service.generate_personalized_content("learning_path", intern_data)
            )
            
            # Save to database
            db = SessionLocal()
            try:
                create_personalized_learning_path(db, intern_id, learning_path)
                
                # Notify intern about new learning path
                send_learning_path_notification.delay(intern_id, learning_path)
                
                logger.info(f"Learning path generated for intern {intern_id}")
                return {"status": "completed", "intern_id": intern_id}
                
            finally:
                db.close()
                
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Learning path generation failed for intern {intern_id}: {str(exc)}")
        return {"status": "failed", "intern_id": intern_id, "error": str(exc)}

@celery_app.task
def cleanup_expired_notifications():
    """Daily cleanup task for expired notifications"""
    
    try:
        from app.services.notification_service import notification_service
        
        db = SessionLocal()
        try:
            count = notification_service.clean_expired_notifications(db)
            logger.info(f"Cleaned up {count} expired notifications")
            return {"status": "completed", "cleaned_count": count}
            
        finally:
            db.close()
            
    except Exception as exc:
        logger.error(f"Notification cleanup failed: {str(exc)}")
        return {"status": "failed", "error": str(exc)}

@celery_app.task
def generate_weekly_reports():
    """Generate weekly performance reports"""
    
    try:
        from app.services.analytics_service import generate_weekly_analytics
        
        db = SessionLocal()
        try:
            # Generate reports for all active interns
            reports = generate_weekly_analytics(db)
            
            # Send reports to mentors and admins
            for report in reports:
                send_weekly_report_email.delay(report)
            
            logger.info(f"Generated {len(reports)} weekly reports")
            return {"status": "completed", "reports_count": len(reports)}
            
        finally:
            db.close()
            
    except Exception as exc:
        logger.error(f"Weekly report generation failed: {str(exc)}")
        return {"status": "failed", "error": str(exc)}

@celery_app.task
def send_analysis_complete_notification(intern_id: int, analysis_result: Dict[str, Any]):
    """Send notification when resume analysis is complete"""
    
    try:
        db = SessionLocal()
        try:
            from app.services.intern_service import get_intern_by_id
            from app.services.notification_service import send_notification, NotificationType
            
            intern = get_intern_by_id(db, intern_id)
            if intern:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    loop.run_until_complete(
                        send_notification(
                            db,
                            intern.user_id,
                            NotificationType.SYSTEM_ANNOUNCEMENT,
                            "Resume Analysis Complete",
                            f"Your resume analysis is ready! Overall score: {analysis_result.get('overall_score', 'N/A')}/100",
                            data={"analysis_id": analysis_result.get("id")},
                            action_url="/resume-analysis",
                            action_text="View Analysis"
                        )
                    )
                finally:
                    loop.close()
                    
        finally:
            db.close()
            
    except Exception as exc:
        logger.error(f"Failed to send analysis notification to intern {intern_id}: {str(exc)}")

@celery_app.task
def send_admin_alert(subject: str, message: str):
    """Send alert to administrators"""
    
    admin_emails = settings.ADMIN_EMAILS or ["admin@yourdomain.com"]
    
    for email in admin_emails:
        send_notification_email.delay(
            email=email,
            subject=f"[ALERT] {subject}",
            body=message,
            html_body=f"<div style='color: red;'><h3>Alert</h3><p>{message}</p></div>"
        )

# Periodic tasks setup
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'cleanup-expired-notifications': {
        'task': 'app.tasks.background_tasks.cleanup_expired_notifications',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'generate-weekly-reports': {
        'task': 'app.tasks.background_tasks.generate_weekly_reports',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Monday at 8 AM
    },
}

celery_app.conf.timezone = 'UTC'
