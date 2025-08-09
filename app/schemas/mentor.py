from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator
from enum import Enum

class MentorBase(BaseModel):
    designation: Optional[str] = None
    department: Optional[str] = None
    company: Optional[str] = None
    years_of_experience: Optional[int] = None
    expertise_areas: Optional[List[str]] = []
    max_interns: int = 5
    mentorship_style: Optional[str] = None
    office_location: Optional[str] = None
    timezone: Optional[str] = None
    preferred_communication: Optional[List[str]] = []
    
    @validator('years_of_experience')
    def validate_experience(cls, v):
        if v is not None and (v < 0 or v > 50):
            raise ValueError('Years of experience must be between 0 and 50')
        return v
    
    @validator('max_interns')
    def validate_max_interns(cls, v):
        if v < 1 or v > 20:
            raise ValueError('Max interns must be between 1 and 20')
        return v

class MentorCreate(MentorBase):
    pass

class MentorUpdate(BaseModel):
    designation: Optional[str] = None
    department: Optional[str] = None
    company: Optional[str] = None
    years_of_experience: Optional[int] = None
    expertise_areas: Optional[List[str]] = None
    max_interns: Optional[int] = None
    is_available: Optional[bool] = None
    mentorship_style: Optional[str] = None
    office_location: Optional[str] = None
    timezone: Optional[str] = None
    preferred_communication: Optional[List[str]] = None

class MentorResponse(MentorBase):
    id: int
    user_id: int
    current_interns_count: int = 0
    is_available: bool = True
    total_interns_mentored: int = 0
    average_intern_rating: float = 0.0
    feedback_response_time: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class MentorList(BaseModel):
    mentors: List[MentorResponse]
    total: int
    skip: int
    limit: int

class MentorshipRequest(BaseModel):
    mentor_id: int
    intern_id: int
    message: Optional[str] = None

class MentorFeedback(BaseModel):
    intern_id: int
    title: str
    content: str
    rating: Optional[int] = None
    feedback_type: str = "general"
    
    @validator('rating')
    def validate_rating(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('Rating must be between 1 and 5')
        return v

class MentorDashboard(BaseModel):
    """Mentor dashboard data"""
    mentor_info: Dict[str, Any]
    assigned_interns: List[Dict[str, Any]]
    pending_tasks: List[Dict[str, Any]]
    recent_submissions: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]
    upcoming_deadlines: List[Dict[str, Any]]

class MentorPerformance(BaseModel):
    """Mentor performance metrics"""
    mentor_id: int
    total_interns: int
    active_interns: int
    completion_rate: float
    average_intern_score: float
    response_time_hours: float
    feedback_quality_score: float
    satisfaction_rating: float
    strengths: List[str]
    improvement_areas: List[str]
