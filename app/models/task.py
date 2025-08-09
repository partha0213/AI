from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base

class TaskStatus(enum.Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    REVISION_REQUIRED = "revision_required"

class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    
    # Basic Information
    title = Column(String, nullable=False)
    description = Column(Text)
    instructions = Column(Text)
    priority = Column(String, default=TaskPriority.MEDIUM.value)
    
    # Assignment Details
    assigned_intern_id = Column(Integer, ForeignKey("interns.id"))
    created_by_mentor_id = Column(Integer, ForeignKey("mentors.id"))
    
    # Task Metadata
    category = Column(String)  # e.g., "Research", "Development", "Analysis"
    tags = Column(JSON)  # List of relevant tags
    estimated_hours = Column(Float)
    difficulty_level = Column(String)  # Beginner, Intermediate, Advanced
    
    # Timeline
    assigned_date = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime)
    started_date = Column(DateTime)
    completed_date = Column(DateTime)
    
    # Status and Progress
    status = Column(String, default=TaskStatus.ASSIGNED.value)
    progress_percentage = Column(Float, default=0.0)
    
    # Submission Details
    submission_text = Column(Text)
    submission_files = Column(JSON)  # List of file URLs/paths
    submission_date = Column(DateTime)
    
    # Evaluation
    score = Column(Float)
    ai_feedback = Column(JSON)
    mentor_feedback = Column(Text)
    auto_graded = Column(Boolean, default=False)
    
    # Requirements
    required_skills = Column(JSON)  # List of skills needed
    learning_objectives = Column(JSON)  # What intern should learn
    deliverables = Column(JSON)  # Expected outputs
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assigned_intern = relationship("Intern", back_populates="tasks")
    created_by_mentor = relationship("Mentor", back_populates="tasks_created")
    ai_evaluations = relationship("AIEvaluation", back_populates="task")
