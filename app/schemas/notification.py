from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, validator
from enum import Enum

class NotificationType(str, Enum):
    TASK_ASSIGNED = "task_assigned"
    TASK_SUBMITTED = "task_submitted"
    FEEDBACK_RECEIVED = "feedback_received"
    LEARNING_MILESTONE = "learning_milestone"
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    MENTOR_ASSIGNED = "mentor_assigned"

class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class NotificationBase(BaseModel):
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    @validator('title')
    def validate_title(cls, v):
        if len(v.strip()) < 3:
            raise ValueError('Title must be at least 3 characters')
        return v.strip()

class NotificationCreate(NotificationBase):
    user_id: int

class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_read: bool = False
    is_sent_email: bool = False
    is_sent_push: bool = False
    created_at: datetime
    read_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
