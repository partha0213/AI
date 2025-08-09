"""
Service layer for the AI Virtual Internship Platform

This package contains all business logic services:
- auth_service: Authentication and authorization
- intern_service: Intern management and operations
- mentor_service: Mentor management and mentorship
- task_service: Task creation, assignment, and evaluation
- learning_service: Learning modules and progress tracking
- ai_service: AI agent coordination and processing
- analytics_service: Analytics and reporting
- notification_service: Notifications and communications
- email_service: Email sending and templates
"""

from .auth_service import *
from .intern_service import *
from .mentor_service import *
from .task_service import *
from .learning_service import *
from .ai_service import *
from .analytics_service import *
from .notification_service import *

__all__ = [
    # Auth services
    "authenticate_user",
    "create_user",
    "get_user_by_id",
    "get_user_by_email",
    "get_user_by_username",
    "update_user_password",
    "verify_user_email",
    
    # Intern services
    "create_intern_profile",
    "get_intern_by_id",
    "get_intern_by_user_id",
    "update_intern_profile",
    "get_all_interns",
    "upload_resume",
    "assess_skills",
    
    # Mentor services
    "create_mentor_profile",
    "get_mentor_by_id", 
    "get_mentor_by_user_id",
    "update_mentor_profile",
    "get_all_mentors",
    "assign_intern_to_mentor",
    "get_mentor_interns",
    "submit_mentor_feedback",
    
    # Task services
    "create_task",
    "get_task_by_id",
    "get_tasks_by_intern",
    "get_tasks_by_mentor",
    "update_task",
    "submit_task",
    "evaluate_task_submission",
    
    # Learning services  
    "create_learning_module",
    "get_learning_module",
    "get_learning_modules",
    "start_module_progress",
    "update_learning_progress",
    "submit_quiz_attempt",
    "generate_certificate",
    
    # AI services
    "analyze_resume",
    "assess_skills_ai",
    "auto_grade_submission",
    "generate_personalized_content",
    "recommend_next_modules",
    
    # Analytics services
    "calculate_engagement_metrics",
    "generate_performance_report",
    "get_trend_analysis",
    "calculate_success_rates",
    
    # Notification services
    "send_notification",
    "send_task_assignment_notification",
    "send_feedback_notification",
    "broadcast_announcement"
]
