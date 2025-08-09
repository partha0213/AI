from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base

class NotificationType(enum.Enum):
    TASK_ASSIGNED = "task_assigned"
    TASK_SUBMITTED = "task_submitted" 
    FEEDBACK_RECEIVED = "feedback_received"
    LEARNING_MILESTONE = "learning_milestone"
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    MENTOR_ASSIGNED = "mentor_assigned"

class NotificationPriority(enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    
    # Target user
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Notification details
    type = Column(String, nullable=False)
    priority = Column(String, default=NotificationPriority.NORMAL.value)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    
    # Additional data
    data = Column(JSON)  # Additional context data
    action_url = Column(String)  # URL for action button
    action_text = Column(String)  # Text for action button
    
    # Status
    is_read = Column(Boolean, default=False)
    is_sent_email = Column(Boolean, default=False)
    is_sent_push = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime)
    expires_at = Column(DateTime)  # Optional expiration
    
    # Relationships
    user = relationship("User")
