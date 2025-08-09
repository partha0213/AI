from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base

class AISessionType(enum.Enum):
    ASSESSMENT = "assessment"
    EVALUATION = "evaluation"
    CUSTOMIZATION = "customization"
    TASK_MANAGEMENT = "task_management"
    ONBOARDING = "onboarding"

class AISession(Base):
    __tablename__ = "ai_sessions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Session details
    session_type = Column(String, nullable=False)
    agent_name = Column(String, nullable=False)
    
    # Related entities
    user_id = Column(Integer, ForeignKey("users.id"))
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    
    # Input/Output
    input_data = Column(JSON)
    output_data = Column(JSON)
    
    # Processing details
    processing_time = Column(Float)  # in seconds
    status = Column(String, default="completed")  # pending, completed, failed
    error_message = Column(Text)
    
    # Metrics
    tokens_used = Column(Integer)
    cost = Column(Float)
    confidence_score = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    user = relationship("User")
    intern = relationship("Intern")
    task = relationship("Task")
