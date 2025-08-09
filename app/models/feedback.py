from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Float, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base

class FeedbackType(enum.Enum):
    TASK = "task"
    GENERAL = "general"
    MENTOR = "mentor"
    LEARNING = "learning"

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    
    # References
    mentor_id = Column(Integer, ForeignKey("mentors.id"))
    intern_id = Column(Integer, ForeignKey("interns.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    
    # Feedback Details
    feedback_type = Column(String, default=FeedbackType.TASK.value)
    title = Column(String)
    content = Column(Text, nullable=False)
    rating = Column(Integer)  # 1-5 scale
    
    # Status
    is_read = Column(Boolean, default=False)
    is_acknowledged = Column(Boolean, default=False)
    
    # AI Analysis
    sentiment_score = Column(Float)  # AI sentiment analysis
    key_points = Column(JSON)  # Extracted key points
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime)
    acknowledged_at = Column(DateTime)
    
    # Relationships
    mentor = relationship("Mentor", back_populates="feedback_given")
    intern = relationship("Intern", back_populates="feedback_received")
    task = relationship("Task")
