# app/api/v1/feedback.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.feedback_service import create_feedback, get_user_feedback

router = APIRouter()

@router.post("/", response_model=FeedbackResponse)
async def create_feedback_endpoint(
    feedback: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_mentor)
):
    """Create new feedback"""
    return await create_feedback(db, feedback, current_user.id)

@router.get("/intern/{intern_id}")
async def get_intern_feedback(
    intern_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Get feedback for intern"""
    return await get_user_feedback(db, intern_id)
