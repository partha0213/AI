from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base

class Mentor(Base):
    __tablename__ = "mentors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    # Professional Information
    designation = Column(String)
    department = Column(String)
    company = Column(String)
    years_of_experience = Column(Integer)
    expertise_areas = Column(JSON)  # List of expertise areas
    
    # Mentorship Details
    max_interns = Column(Integer, default=5)
    current_interns_count = Column(Integer, default=0)
    is_available = Column(Boolean, default=True)
    mentorship_style = Column(String)
    
    # Contact Information
    office_location = Column(String)
    timezone = Column(String)
    preferred_communication = Column(JSON)  # email, slack, teams, etc.
    
    # Performance Metrics
    total_interns_mentored = Column(Integer, default=0)
    average_intern_rating = Column(Integer, default=0)
    feedback_response_time = Column(Integer)  # in hours
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="mentor_profile")
    assigned_interns = relationship("Intern", back_populates="assigned_mentor")
    tasks_created = relationship("Task", back_populates="created_by_mentor")
    feedback_given = relationship("Feedback", back_populates="mentor")
