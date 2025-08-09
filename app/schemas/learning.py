from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator
from enum import Enum

class ModuleDifficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class ModuleType(str, Enum):
    VIDEO = "video"
    ARTICLE = "article"
    INTERACTIVE = "interactive"
    QUIZ = "quiz"
    PROJECT = "project"

class LearningModuleBase(BaseModel):
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    module_type: ModuleType = ModuleType.ARTICLE
    track: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = []
    difficulty: ModuleDifficulty = ModuleDifficulty.BEGINNER
    estimated_duration: Optional[int] = None  # in minutes
    
    @validator('title')
    def validate_title(cls, v):
        if len(v.strip()) < 3:
            raise ValueError('Title must be at least 3 characters')
        return v.strip()
    
    @validator('estimated_duration')
    def validate_duration(cls, v):
        if v is not None and (v <= 0 or v > 600):  # max 10 hours
            raise ValueError('Duration must be between 1 and 600 minutes')
        return v

class LearningModuleCreate(LearningModuleBase):
    prerequisites: Optional[List[int]] = []
    learning_objectives: Optional[List[str]] = []
    video_url: Optional[str] = None
    materials: Optional[Dict[str, Any]] = None
    order_index: int = 0

class LearningModuleResponse(LearningModuleBase):
    id: int
    prerequisites: Optional[List[int]] = []
    learning_objectives: Optional[List[str]] = []
    video_url: Optional[str] = None
    materials: Optional[Dict[str, Any]] = None
    created_by: int
    is_active: bool = True
    order_index: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class LearningProgressResponse(BaseModel):
    id: int
    intern_id: int
    module_id: int
    status: str
    completion_percentage: float
    time_spent: int  # in minutes
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    bookmarked: bool = False
    quiz_scores: Optional[List[float]] = []
    average_score: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class QuizCreate(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    module_id: int
    questions: List[Dict[str, Any]]
    time_limit: Optional[int] = None  # in minutes
    passing_score: float = 70.0
    max_attempts: int = 3
    randomize_questions: bool = True
    show_results_immediately: bool = True
    allow_review: bool = True
    
    @validator('passing_score')
    def validate_passing_score(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Passing score must be between 0 and 100')
        return v
    
    @validator('max_attempts')
    def validate_max_attempts(cls, v):
        if v < 1 or v > 10:
            raise ValueError('Max attempts must be between 1 and 10')
        return v

class QuizResponse(QuizCreate):
    id: int
    created_by: int
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class QuizAttemptCreate(BaseModel):
    answers: List[Dict[str, Any]]
    started_at: datetime
    
    @validator('answers')
    def validate_answers(cls, v):
        if not v:
            raise ValueError('Answers cannot be empty')
        return v

class QuizAttemptResponse(QuizAttemptCreate):
    id: int
    quiz_id: int
    intern_id: int
    attempt_number: int
    score: Optional[float] = None
    passed: Optional[bool] = None
    completed_at: Optional[datetime] = None
    time_taken: Optional[int] = None  # in seconds
    ai_feedback: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class CertificateResponse(BaseModel):
    id: int
    intern_id: int
    module_id: Optional[int] = None
    certificate_type: str
    title: str
    description: Optional[str] = None
    certificate_id: str
    issued_date: datetime
    certificate_url: Optional[str] = None
    skills_demonstrated: Optional[List[str]] = []
    verification_data: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class LearningPath(BaseModel):
    """Personalized learning path"""
    track: str
    modules: List[Dict[str, Any]]
    total_duration: int  # in minutes
    completed_modules: int
    in_progress_modules: int
    estimated_completion_weeks: int
    difficulty_progression: List[str]
    milestones: List[Dict[str, Any]]

class LearningRecommendations(BaseModel):
    """AI-generated learning recommendations"""
    next_modules: List[Dict[str, Any]]
    skill_gaps: List[str]
    suggested_projects: List[Dict[str, Any]]
    study_plan: Dict[str, Any]
    estimated_timeline: str
    personalization_score: float

class LearningAnalytics(BaseModel):
    """Learning analytics data"""
    summary: Dict[str, Any]
    progress_analysis: Dict[str, Any]
    module_performance: Dict[str, Any]
    quiz_analytics: Dict[str, Any]
    engagement_analysis: Dict[str, Any]
    track_comparison: Optional[Dict[str, Any]] = None
