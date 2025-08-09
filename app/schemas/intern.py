from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator
from enum import Enum

from app.utils.validators import (
    validate_github_url_field,
    validate_linkedin_url_field,
    validate_skills_field
)

class InternStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    SUSPENDED = "suspended"

class ExperienceLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class InternBase(BaseModel):
    university: Optional[str] = None
    degree: Optional[str] = None
    graduation_year: Optional[int] = None
    major: Optional[str] = None
    gpa: Optional[float] = None
    program_track: Optional[str] = None
    experience_level: ExperienceLevel = ExperienceLevel.BEGINNER
    
    @validator('gpa')
    def validate_gpa(cls, v):
        if v is not None and (v < 0.0 or v > 4.0):
            raise ValueError('GPA must be between 0.0 and 4.0')
        return v
    
    @validator('graduation_year')
    def validate_graduation_year(cls, v):
        current_year = datetime.now().year
        if v is not None and (v < current_year - 10 or v > current_year + 10):
            raise ValueError('Graduation year must be reasonable')
        return v

class InternCreate(InternBase):
    skills: Optional[List[str]] = []
    previous_experience: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    
    @validator('skills')
    def validate_skills(cls, v):
        if v:
            return validate_skills_field(v)
        return v
    
    @validator('github_url')
    def validate_github_url(cls, v):
        if v:
            return validate_github_url_field(v)
        return v
    
    @validator('linkedin_url')
    def validate_linkedin_url(cls, v):
        if v:
            return validate_linkedin_url_field(v)
        return v

class InternUpdate(BaseModel):
    university: Optional[str] = None
    degree: Optional[str] = None
    graduation_year: Optional[int] = None
    major: Optional[str] = None
    gpa: Optional[float] = None
    skills: Optional[List[str]] = None
    experience_level: Optional[ExperienceLevel] = None
    previous_experience: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    status: Optional[InternStatus] = None
    
    @validator('skills')
    def validate_skills(cls, v):
        if v:
            return validate_skills_field(v)
        return v

class InternResponse(InternBase):
    id: int
    intern_id: str
    user_id: int
    skills: Optional[List[str]] = []
    previous_experience: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: InternStatus
    assessment_score: Optional[float] = None
    skill_assessment: Optional[Dict[str, Any]] = None
    personality_traits: Optional[Dict[str, Any]] = None
    learning_style: Optional[str] = None
    completed_tasks: int = 0
    total_tasks: int = 0
    performance_score: float = 0.0
    assigned_mentor_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class InternList(BaseModel):
    interns: List[InternResponse]
    total: int
    skip: int
    limit: int

class InternProfileComplete(BaseModel):
    """Complete intern profile with all related data"""
    intern: InternResponse
    user: dict
    mentor: Optional[dict] = None
    recent_tasks: List[dict] = []
    learning_progress: dict = {}
    performance_metrics: dict = {}
    
    class Config:
        from_attributes = True

class InternSearch(BaseModel):
    """Search criteria for interns"""
    program_track: Optional[str] = None
    experience_level: Optional[ExperienceLevel] = None
    status: Optional[InternStatus] = None
    skills: Optional[List[str]] = None
    university: Optional[str] = None
    graduation_year: Optional[int] = None
    has_mentor: Optional[bool] = None
    performance_min: Optional[float] = None
    performance_max: Optional[float] = None

class InternStats(BaseModel):
    """Intern statistics"""
    total_interns: int
    active_interns: int
    completed_interns: int
    pending_interns: int
    average_performance: float
    completion_rate: float
    
class InternProgress(BaseModel):
    """Intern progress summary"""
    intern_id: int
    overall_progress: float
    tasks_completed: int
    tasks_total: int
    learning_modules_completed: int
    learning_modules_total: int
    skill_improvements: Dict[str, float]
    recent_achievements: List[str]
    next_milestones: List[str]
