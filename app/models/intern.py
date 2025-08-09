from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base

class InternStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    SUSPENDED = "suspended"

class Intern(Base):
    __tablename__ = "interns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    intern_id = Column(String, unique=True, index=True)  # Generated intern ID
    
    # Profile Information
    university = Column(String)
    degree = Column(String)
    graduation_year = Column(Integer)
    major = Column(String)
    gpa = Column(Float)
    
    # Skills and Experience
    skills = Column(JSON)  # List of skills
    experience_level = Column(String)  # Beginner, Intermediate, Advanced
    previous_experience = Column(Text)
    portfolio_url = Column(String)
    linkedin_url = Column(String)
    github_url = Column(String)
    
    # Internship Details
    program_track = Column(String)  # e.g., "Data Science", "Web Development"
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    status = Column(String, default=InternStatus.PENDING.value)
    
    # AI Assessment Results
    assessment_score = Column(Float)
    skill_assessment = Column(JSON)  # Detailed skill breakdown
    personality_traits = Column(JSON)
    learning_style = Column(String)
    
    # Progress Tracking
    completed_tasks = Column(Integer, default=0)
    total_tasks = Column(Integer, default=0)
    performance_score = Column(Float, default=0.0)
    
    # Mentorship
    assigned_mentor_id = Column(Integer, ForeignKey("mentors.id"))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="intern_profile")
    assigned_mentor = relationship("Mentor", back_populates="assigned_interns")
    tasks = relationship("Task", back_populates="assigned_intern")
    learning_progress = relationship("LearningProgress", back_populates="intern")
    feedback_received = relationship("Feedback", back_populates="intern")
