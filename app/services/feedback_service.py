# app/services/feedback_service.py
from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate


async def create_feedback(db: Session, feedback: FeedbackCreate, mentor_id: int) -> Feedback:
    """
    Create a feedback record. If task_id is provided in FeedbackCreate, it will be linked.
    """
    fb = Feedback(
        title=feedback.title,
        content=feedback.content,
        feedback_type=feedback.feedback_type.value,
        rating=feedback.rating,
        mentor_id=mentor_id,
        intern_id=feedback.intern_id,
        task_id=feedback.task_id,
        is_read=False,
        is_acknowledged=False,
        sentiment_score=None,
        key_points=None,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


async def get_user_feedback(db: Session, intern_id: int) -> List[Feedback]:
    """
    Return latest feedback entries for an intern (most recent first).
    """
    return (
        db.query(Feedback)
        .filter(Feedback.intern_id == intern_id)
        .order_by(Feedback.created_at.desc())
        .all()
    )
