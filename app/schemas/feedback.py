from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, validator
from enum import Enum

class FeedbackType(str, Enum):
    TASK = "task"
    GENERAL = "general"
    MENTOR = "mentor"
    LEARNING = "learning"

class FeedbackBase(BaseModel):
    title: str
    content: str
    feedback_type: FeedbackType = FeedbackType.GENERAL
    rating: Optional[int] = None
    
    @validator('title')
    def validate_title(cls, v):
        if len(v.strip()) < 3:
            raise ValueError('Title must be at least 3 characters')
        return v.strip()
    
    @validator('content')
    def validate_content(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('Content must be at least 10 characters')
        return v.strip()
    
    @validator('rating')
    def validate_rating(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('Rating must be between 1 and 5')
        return v

class FeedbackCreate(FeedbackBase):
    intern_id: int
    task_id: Optional[int] = None

class FeedbackResponse(FeedbackBase):
    id: int
    mentor_id: int
    intern_id: int
    task_id: Optional[int] = None
    is_read: bool = False
    is_acknowledged: bool = False
    sentiment_score: Optional[float] = None
    key_points: Optional[list] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
