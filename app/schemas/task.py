from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator
from enum import Enum

class TaskStatus(str, Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    REVISION_REQUIRED = "revision_required"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    category: Optional[str] = None
    tags: Optional[List[str]] = []
    estimated_hours: Optional[float] = None
    difficulty_level: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    
    @validator('title')
    def validate_title(cls, v):
        if len(v.strip()) < 3:
            raise ValueError('Title must be at least 3 characters')
        return v.strip()
    
    @validator('estimated_hours')
    def validate_estimated_hours(cls, v):
        if v is not None and (v <= 0 or v > 200):
            raise ValueError('Estimated hours must be between 0 and 200')
        return v

class TaskCreate(TaskBase):
    assigned_intern_id: int
    due_date: Optional[datetime] = None
    required_skills: Optional[List[str]] = []
    learning_objectives: Optional[List[str]] = []
    deliverables: Optional[List[str]] = []

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    priority: Optional[TaskPriority] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    estimated_hours: Optional[float] = None
    difficulty_level: Optional[DifficultyLevel] = None
    due_date: Optional[datetime] = None
    status: Optional[TaskStatus] = None
    progress_percentage: Optional[float] = None
    started_date: Optional[datetime] = None
    
    @validator('progress_percentage')
    def validate_progress(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Progress percentage must be between 0 and 100')
        return v

class TaskResponse(TaskBase):
    id: int
    assigned_intern_id: int
    created_by_mentor_id: int
    assigned_date: datetime
    due_date: Optional[datetime] = None
    started_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    status: TaskStatus
    progress_percentage: float = 0.0
    submission_text: Optional[str] = None
    submission_files: Optional[List[str]] = []
    submission_date: Optional[datetime] = None
    score: Optional[float] = None
    ai_feedback: Optional[Dict[str, Any]] = None
    mentor_feedback: Optional[str] = None
    auto_graded: bool = False
    required_skills: Optional[List[str]] = []
    learning_objectives: Optional[List[str]] = []
    deliverables: Optional[List[str]] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TaskSubmission(BaseModel):
    submission_text: str
    submission_files: Optional[List[str]] = []
    
    @validator('submission_text')
    def validate_submission_text(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('Submission must be at least 10 characters')
        return v.strip()

class TaskEvaluation(BaseModel):
    score: float
    feedback: str
    passed: bool
    evaluation_criteria: Optional[Dict[str, float]] = None
    suggestions: Optional[List[str]] = []
    
    @validator('score')
    def validate_score(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Score must be between 0 and 100')
        return v

class TaskList(BaseModel):
    tasks: List[TaskResponse]
    total: int
    skip: int
    limit: int

class TaskStats(BaseModel):
    """Task statistics"""
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    overdue_tasks: int
    average_completion_time: float
    average_score: float
    completion_rate: float

class TaskFilter(BaseModel):
    """Task filtering options"""
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    difficulty_level: Optional[DifficultyLevel] = None
    category: Optional[str] = None
    assigned_intern_id: Optional[int] = None
    created_by_mentor_id: Optional[int] = None
    due_date_from: Optional[datetime] = None
    due_date_to: Optional[datetime] = None
    overdue_only: bool = False

class TaskAnalytics(BaseModel):
    """Task analytics data"""
    summary: TaskStats
    distribution: Dict[str, int]
    completion_analysis: Dict[str, Any]
    difficulty_analysis: Dict[str, Any]
    time_analysis: Dict[str, Any]
    category_performance: Dict[str, Any]
