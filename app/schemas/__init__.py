"""
Pydantic schemas for the AI Virtual Internship Platform

This package contains all Pydantic models for request/response validation:
- user: User-related schemas
- intern: Intern-specific schemas  
- mentor: Mentor-specific schemas
- task: Task management schemas
- learning: Learning and progress schemas
- ai_agent: AI agent interaction schemas
- analytics: Analytics and reporting schemas
"""

from .user import *
from .intern import *
from .mentor import *
from .task import *
from .learning import *
from .ai_agent import *
from .analytics import *
from .feedback import *
from .notification import *

__all__ = [
    # User schemas
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "Token",
    "PasswordReset",
    
    # Intern schemas
    "InternBase",
    "InternCreate",
    "InternUpdate",
    "InternResponse",
    "InternList",
    "InternProfileComplete",
    
    # Mentor schemas
    "MentorBase",
    "MentorCreate", 
    "MentorUpdate",
    "MentorResponse",
    "MentorList",
    "MentorshipRequest",
    "MentorFeedback",
    
    # Task schemas
    "TaskBase",
    "TaskCreate",
    "TaskUpdate", 
    "TaskResponse",
    "TaskSubmission",
    "TaskList",
    "TaskEvaluation",
    
    # Learning schemas
    "LearningModuleBase",
    "LearningModuleCreate",
    "LearningModuleResponse",
    "LearningProgressResponse",
    "QuizCreate",
    "QuizResponse",
    "QuizAttemptCreate",
    "QuizAttemptResponse",
    "CertificateResponse",
    
    # AI Agent schemas
    "AIRequestBase",
    "AssessmentRequest",
    "EvaluationRequest",
    "CustomizationRequest",
    "AIResponse",
    
    # Analytics schemas
    "DashboardMetrics",
    "InternAnalytics",
    "MentorAnalytics",
    "TaskAnalytics",
    "LearningAnalytics",
    "SystemMetrics",
    
    # Feedback schemas
    "FeedbackBase",
    "FeedbackCreate",
    "FeedbackResponse",
    
    # Notification schemas
    "NotificationBase",
    "NotificationCreate",
    "NotificationResponse"
]
