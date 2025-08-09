from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging

from app.core.exceptions import NotFoundError, ValidationError
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.user import User, UserRole
from app.schemas.notification import NotificationCreate
from app.utils.email import send_email
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    """Comprehensive notification service for various communication needs"""
    
    def __init__(self):
        self.email_templates = {
            "welcome": {
                "subject": "Welcome to {platform_name}!",
                "template": "welcome_email.html"
            },
            "task_assigned": {
                "subject": "New Task Assigned: {task_title}",
                "template": "task_assigned.html"
            },
            "task_submitted": {
                "subject": "Task Submitted: {task_title}",
                "template": "task_submitted.html"
            },
            "feedback_received": {
                "subject": "New Feedback Available",
                "template": "feedback_received.html"
            },
            "mentor_assigned": {
                "subject": "Mentor Assigned - Welcome to the Program",
                "template": "mentor_assigned.html"
            },
            "certificate_earned": {
                "subject": "Congratulations! Certificate Earned",
                "template": "certificate_earned.html"
            }
        }

    async def send_notification(
        self,
        db: Session,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None,
        send_email: bool = True,
        expires_at: Optional[datetime] = None
    ) -> Notification:
        """Send notification to user"""
        
        try:
            # Create notification record
            notification = Notification(
                user_id=user_id,
                type=notification_type.value,
                priority=priority.value,
                title=title,
                message=message,
                data=data,
                action_url=action_url,
                action_text=action_text,
                expires_at=expires_at
            )
            
            db.add(notification)
            db.commit()
            db.refresh(notification)
            
            # Send real-time notification via WebSocket
            await self._send_realtime_notification(user_id, notification)
            
            # Send email notification if enabled
            if send_email and settings.EMAIL_NOTIFICATIONS_ENABLED:
                await self._send_email_notification(db, user_id, notification)
                notification.is_sent_email = True
                db.commit()
            
            logger.info(f"Notification sent to user {user_id}: {title}")
            return notification
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            raise ValidationError(f"Failed to send notification: {str(e)}")

    async def send_task_assignment_notification(
        self,
        db: Session,
        intern_id: int,
        task_data: Dict[str, Any],
        mentor_name: str
    ) -> Notification:
        """Send task assignment notification to intern"""
        
        from app.services.intern_service import get_intern_by_id
        intern = get_intern_by_id(db, intern_id)
        if not intern:
            raise NotFoundError("Intern not found")
        
        title = f"New Task Assigned: {task_data.get('title', 'Untitled Task')}"
        message = f"You have been assigned a new task '{task_data['title']}' by {mentor_name}."
        
        if task_data.get('due_date'):
            message += f" Due date: {task_data['due_date'].strftime('%B %d, %Y')}"
        
        notification_data = {
            "task_id": task_data.get('id'),
            "task_title": task_data.get('title'),
            "mentor_name": mentor_name,
            "due_date": task_data.get('due_date').isoformat() if task_data.get('due_date') else None,
            "priority": task_data.get('priority'),
            "estimated_hours": task_data.get('estimated_hours')
        }
        
        return await self.send_notification(
            db=db,
            user_id=intern.user_id,
            notification_type=NotificationType.TASK_ASSIGNED,
            title=title,
            message=message,
            data=notification_data,
            priority=self._get_priority_from_task_priority(task_data.get('priority', 'medium')),
            action_url=f"/tasks/{task_data.get('id')}",
            action_text="View Task"
        )

    async def send_task_submission_notification(
        self,
        db: Session,
        mentor_id: int,
        task_data: Dict[str, Any],
        intern_name: str
    ) -> Notification:
        """Send task submission notification to mentor"""
        
        from app.services.mentor_service import get_mentor_by_id
        mentor = get_mentor_by_id(db, mentor_id)
        if not mentor:
            raise NotFoundError("Mentor not found")
        
        title = f"Task Submitted: {task_data.get('title', 'Untitled Task')}"
        message = f"{intern_name} has submitted the task '{task_data['title']}' for review."
        
        notification_data = {
            "task_id": task_data.get('id'),
            "task_title": task_data.get('title'),
            "intern_name": intern_name,
            "submission_date": datetime.utcnow().isoformat(),
            "requires_review": True
        }
        
        return await self.send_notification(
            db=db,
            user_id=mentor.user_id,
            notification_type=NotificationType.TASK_SUBMITTED,
            title=title,
            message=message,
            data=notification_data,
            priority=NotificationPriority.HIGH,
            action_url=f"/tasks/{task_data.get('id')}/review",
            action_text="Review Task"
        )

    async def send_feedback_notification(
        self,
        db: Session,
        intern_id: int,
        feedback_data: Dict[str, Any],
        mentor_name: str
    ) -> Notification:
        """Send feedback notification to intern"""
        
        from app.services.intern_service import get_intern_by_id
        intern = get_intern_by_id(db, intern_id)
        if not intern:
            raise NotFoundError("Intern not found")
        
        title = "New Feedback Received"
        message = f"You have received new feedback from {mentor_name}"
        
        if feedback_data.get('task_title'):
            message += f" on task '{feedback_data['task_title']}'"
        
        if feedback_data.get('rating'):
            message += f". Rating: {feedback_data['rating']}/5"
        
        notification_data = {
            "feedback_id": feedback_data.get('id'),
            "feedback_type": feedback_data.get('type', 'general'),
            "mentor_name": mentor_name,
            "rating": feedback_data.get('rating'),
            "task_id": feedback_data.get('task_id'),
            "task_title": feedback_data.get('task_title')
        }
        
        return await self.send_notification(
            db=db,
            user_id=intern.user_id,
            notification_type=NotificationType.FEEDBACK_RECEIVED,
            title=title,
            message=message,
            data=notification_data,
            priority=NotificationPriority.NORMAL,
            action_url=f"/feedback/{feedback_data.get('id')}",
            action_text="View Feedback"
        )

    async def send_learning_milestone_notification(
        self,
        db: Session,
        intern_id: int,
        milestone_data: Dict[str, Any]
    ) -> Notification:
        """Send learning milestone notification"""
        
        from app.services.intern_service import get_intern_by_id
        intern = get_intern_by_id(db, intern_id)
        if not intern:
            raise NotFoundError("Intern not found")
        
        milestone_type = milestone_data.get('type', 'completion')
        
        if milestone_type == 'module_completed':
            title = f"Module Completed: {milestone_data.get('module_title', 'Learning Module')}"
            message = f"Congratulations! You have completed the learning module '{milestone_data.get('module_title')}'."
        elif milestone_type == 'certificate_earned':
            title = f"Certificate Earned: {milestone_data.get('certificate_title', 'Achievement')}"
            message = f"Great job! You've earned a certificate for '{milestone_data.get('certificate_title')}'."
        elif milestone_type == 'quiz_passed':
            title = f"Quiz Passed: {milestone_data.get('quiz_title', 'Assessment')}"
            message = f"Excellent work! You passed the quiz '{milestone_data.get('quiz_title')}' with a score of {milestone_data.get('score', 0)}%."
        else:
            title = "Learning Milestone Achieved"
            message = "You've reached an important learning milestone. Keep up the great work!"
        
        return await self.send_notification(
            db=db,
            user_id=intern.user_id,
            notification_type=NotificationType.LEARNING_MILESTONE,
            title=title,
            message=message,
            data=milestone_data,
            priority=NotificationPriority.NORMAL,
            action_url=milestone_data.get('action_url', '/learning/progress'),
            action_text="View Progress"
        )

    async def send_mentor_assignment_notification(
        self,
        db: Session,
        intern_id: int,
        mentor_data: Dict[str, Any]
    ) -> List[Notification]:
        """Send mentor assignment notifications to both intern and mentor"""
        
        notifications = []
        
        # Notify intern
        from app.services.intern_service import get_intern_by_id
        intern = get_intern_by_id(db, intern_id)
        if intern:
            intern_notification = await self.send_notification(
                db=db,
                user_id=intern.user_id,
                notification_type=NotificationType.MENTOR_ASSIGNED,
                title="Mentor Assigned",
                message=f"Welcome! {mentor_data['name']} has been assigned as your mentor for the {intern.program_track} program.",
                data={
                    "mentor_id": mentor_data['id'],
                    "mentor_name": mentor_data['name'],
                    "mentor_designation": mentor_data.get('designation'),
                    "mentor_department": mentor_data.get('department'),
                    "program_track": intern.program_track
                },
                priority=NotificationPriority.HIGH,
                action_url=f"/mentors/{mentor_data['id']}",
                action_text="View Mentor Profile"
            )
            notifications.append(intern_notification)
        
        # Notify mentor
        from app.services.mentor_service import get_mentor_by_id
        mentor = get_mentor_by_id(db, mentor_data['id'])
        if mentor:
            mentor_notification = await self.send_notification(
                db=db,
                user_id=mentor.user_id,
                notification_type=NotificationType.MENTOR_ASSIGNED,
                title="New Intern Assigned",
                message=f"A new intern, {intern.user.first_name} {intern.user.last_name}, has been assigned to you in the {intern.program_track} program.",
                data={
                    "intern_id": intern.id,
                    "intern_name": f"{intern.user.first_name} {intern.user.last_name}",
                    "program_track": intern.program_track,
                    "intern_university": intern.university,
                    "intern_experience": intern.experience_level
                },
                priority=NotificationPriority.HIGH,
                action_url=f"/interns/{intern.id}",
                action_text="View Intern Profile"
            )
            notifications.append(mentor_notification)
        
        return notifications

    async def broadcast_system_announcement(
        self,
        db: Session,
        title: str,
        message: str,
        target_roles: Optional[List[UserRole]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        expires_in_days: int = 7,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None
    ) -> List[Notification]:
        """Broadcast system announcement to users"""
        
        # Get target users
        query = db.query(User).filter(User.is_active == True)
        if target_roles:
            query = query.filter(User.role.in_([role.value for role in target_roles]))
        
        users = query.all()
        
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        notifications = []
        
        # Send to each user
        for user in users:
            try:
                notification = await self.send_notification(
                    db=db,
                    user_id=user.id,
                    notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
                    title=title,
                    message=message,
                    data={
                        "announcement_type": "system",
                        "target_roles": [role.value for role in target_roles] if target_roles else ["all"],
                        "broadcast_time": datetime.utcnow().isoformat()
                    },
                    priority=priority,
                    action_url=action_url,
                    action_text=action_text,
                    expires_at=expires_at,
                    send_email=priority in [NotificationPriority.HIGH, NotificationPriority.URGENT]
                )
                notifications.append(notification)
            except Exception as e:
                logger.error(f"Failed to send announcement to user {user.id}: {str(e)}")
        
        logger.info(f"System announcement sent to {len(notifications)} users")
        return notifications

    def get_user_notifications(
        self,
        db: Session,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        skip: int = 0
    ) -> List[Notification]:
        """Get user notifications"""
        
        query = db.query(Notification).filter(Notification.user_id == user_id)
        
        if unread_only:
            query = query.filter(Notification.is_read == False)
        
        # Filter out expired notifications
        query = query.filter(
            or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow()
            )
        )
        
        return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()

    def mark_notification_as_read(
        self,
        db: Session,
        notification_id: int,
        user_id: int
    ) -> Notification:
        """Mark notification as read"""
        
        notification = db.query(Notification).filter(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        ).first()
        
        if not notification:
            raise NotFoundError("Notification not found")
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        
        db.commit()
        db.refresh(notification)
        
        return notification

    def mark_all_notifications_as_read(
        self,
        db: Session,
        user_id: int
    ) -> int:
        """Mark all user notifications as read"""
        
        updated_count = db.query(Notification).filter(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        ).update({
            "is_read": True,
            "read_at": datetime.utcnow()
        })
        
        db.commit()
        return updated_count

    def get_unread_count(self, db: Session, user_id: int) -> int:
        """Get count of unread notifications for user"""
        
        return db.query(Notification).filter(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False,
                or_(
                    Notification.expires_at.is_(None),
                    Notification.expires_at > datetime.utcnow()
                )
            )
        ).count()

    def delete_notification(
        self,
        db: Session,
        notification_id: int,
        user_id: int
    ) -> bool:
        """Delete notification"""
        
        notification = db.query(Notification).filter(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        ).first()
        
        if not notification:
            return False
        
        db.delete(notification)
        db.commit()
        
        return True

    def clean_expired_notifications(self, db: Session) -> int:
        """Clean up expired notifications"""
        
        expired_count = db.query(Notification).filter(
            and_(
                Notification.expires_at.isnot(None),
                Notification.expires_at < datetime.utcnow()
            )
        ).delete()
        
        db.commit()
        
        logger.info(f"Cleaned up {expired_count} expired notifications")
        return expired_count

    async def send_welcome_email(
        self,
        db: Session,
        user_id: int,
        additional_info: Optional[Dict[str, Any]] = None
    ):
        """Send welcome email to new user"""
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError("User not found")
        
        template_data = {
            "user_name": f"{user.first_name} {user.last_name}",
            "platform_name": settings.PROJECT_NAME,
            "login_url": f"{settings.FRONTEND_URL}/login",
            "support_email": settings.SUPPORT_EMAIL,
            **(additional_info or {})
        }
        
        subject = self.email_templates["welcome"]["subject"].format(**template_data)
        
        # Create welcome message
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Welcome to {settings.PROJECT_NAME}!</h2>
            <p>Dear {user.first_name},</p>
            <p>Welcome to our AI-powered virtual internship platform! We're excited to have you join our community.</p>
            <p>Here's what you can expect:</p>
            <ul>
                <li>Personalized learning paths</li>
                <li>Expert mentorship</li>
                <li>Real-world projects</li>
                <li>AI-powered feedback and assessment</li>
            </ul>
            <p><a href="{template_data.get('login_url')}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Get Started</a></p>
            <p>If you have any questions, feel free to contact us at {settings.SUPPORT_EMAIL}</p>
            <p>Best regards,<br>The {settings.PROJECT_NAME} Team</p>
        </div>
        """
        
        plain_content = f"""
        Welcome to {settings.PROJECT_NAME}!
        
        Dear {user.first_name},
        
        Welcome to our AI-powered virtual internship platform! We're excited to have you join our community.
        
        Get started: {template_data.get('login_url')}
        
        If you have any questions, contact us at {settings.SUPPORT_EMAIL}
        
        Best regards,
        The {settings.PROJECT_NAME} Team
        """
        
        await send_email(
            to_emails=[user.email],
            subject=subject,
            body=plain_content,
            html_body=html_content
        )

    async def _send_realtime_notification(self, user_id: int, notification: Notification):
        """Send real-time notification via WebSocket"""
        try:
            from app.core.websocket import manager
            
            realtime_message = {
                "type": "notification",
                "notification": {
                    "id": notification.id,
                    "type": notification.type,
                    "priority": notification.priority,
                    "title": notification.title,
                    "message": notification.message,
                    "data": notification.data,
                    "action_url": notification.action_url,
                    "action_text": notification.action_text,
                    "created_at": notification.created_at.isoformat()
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await manager.send_personal_message(user_id, realtime_message)
            
        except Exception as e:
            logger.error(f"Failed to send real-time notification: {str(e)}")

    async def _send_email_notification(
        self,
        db: Session,
        user_id: int,
        notification: Notification
    ):
        """Send email notification"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return
            
            # Get email template for notification type
            template_key = notification.type
            if template_key not in self.email_templates:
                template_key = "default"
            
            template_data = {
                "user_name": f"{user.first_name} {user.last_name}",
                "notification_title": notification.title,
                "notification_message": notification.message,
                "platform_name": settings.PROJECT_NAME,
                "notification_url": f"{settings.FRONTEND_URL}{notification.action_url}" if notification.action_url else settings.FRONTEND_URL,
                **(notification.data or {})
            }
            
            subject = notification.title
            if template_key in self.email_templates:
                subject = self.email_templates[template_key]["subject"].format(**template_data)
            
            # Create email content
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>{notification.title}</h2>
                <p>Dear {user.first_name},</p>
                <p>{notification.message}</p>
                {f'<p><a href="{template_data.get("notification_url")}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">{notification.action_text or "View Details"}</a></p>' if notification.action_url else ''}
                <p>Best regards,<br>The {settings.PROJECT_NAME} Team</p>
            </div>
            """
            
            plain_content = f"""
            {notification.title}
            
            Dear {user.first_name},
            
            {notification.message}
            
            {f'View details: {template_data.get("notification_url")}' if notification.action_url else ''}
            
            Best regards,
            The {settings.PROJECT_NAME} Team
            """
            
            await send_email(
                to_emails=[user.email],
                subject=subject,
                body=plain_content,
                html_body=html_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")

    def _get_priority_from_task_priority(self, task_priority: str) -> NotificationPriority:
        """Convert task priority to notification priority"""
        priority_map = {
            "low": NotificationPriority.LOW,
            "medium": NotificationPriority.NORMAL,
            "high": NotificationPriority.HIGH,
            "critical": NotificationPriority.URGENT
        }
        return priority_map.get(task_priority.lower(), NotificationPriority.NORMAL)

# Global notification service instance
notification_service = NotificationService()

# Convenience functions for backward compatibility and easier imports
async def send_notification(
    db: Session,
    user_id: int,
    notification_type: NotificationType,
    title: str,
    message: str,
    **kwargs
) -> Notification:
    """Send notification - convenience function"""
    return await notification_service.send_notification(
        db, user_id, notification_type, title, message, **kwargs
    )

async def send_task_assignment_notification(
    db: Session,
    intern_id: int,
    task_data: Dict[str, Any],
    mentor_name: str
) -> Notification:
    """Send task assignment notification - convenience function"""
    return await notification_service.send_task_assignment_notification(
        db, intern_id, task_data, mentor_name
    )

async def send_feedback_notification(
    db: Session,
    intern_id: int,
    feedback_data: Dict[str, Any],
    mentor_name: str
) -> Notification:
    """Send feedback notification - convenience function"""
    return await notification_service.send_feedback_notification(
        db, intern_id, feedback_data, mentor_name
    )

async def broadcast_announcement(
    db: Session,
    title: str,
    message: str,
    target_roles: Optional[List[UserRole]] = None,
    **kwargs
) -> List[Notification]:
    """Broadcast announcement - convenience function"""
    return await notification_service.broadcast_system_announcement(
        db, title, message, target_roles, **kwargs
    )
