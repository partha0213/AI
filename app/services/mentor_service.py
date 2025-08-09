from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime

from app.core.exceptions import MentorNotFoundError, MentorCapacityExceededError
from app.models.mentor import Mentor
from app.models.intern import Intern
from app.models.feedback import Feedback
from app.schemas.mentor import MentorCreate, MentorUpdate, MentorFeedback

def create_mentor_profile(db: Session, mentor: MentorCreate, user_id: int) -> Mentor:
    """Create mentor profile"""
    db_mentor = Mentor(
        user_id=user_id,
        designation=mentor.designation,
        department=mentor.department,
        company=mentor.company,
        years_of_experience=mentor.years_of_experience,
        expertise_areas=mentor.expertise_areas,
        max_interns=mentor.max_interns,
        mentorship_style=mentor.mentorship_style,
        office_location=mentor.office_location,
        timezone=mentor.timezone,
        preferred_communication=mentor.preferred_communication,
        is_available=True
    )
    
    db.add(db_mentor)
    db.commit()
    db.refresh(db_mentor)
    
    return db_mentor

def get_mentor_by_id(db: Session, mentor_id: int) -> Optional[Mentor]:
    """Get mentor by ID"""
    return db.query(Mentor).filter(Mentor.id == mentor_id).first()

def get_mentor_by_user_id(db: Session, user_id: int) -> Optional[Mentor]:
    """Get mentor by user ID"""
    return db.query(Mentor).filter(Mentor.user_id == user_id).first()

def update_mentor_profile(db: Session, mentor_id: int, mentor_update: MentorUpdate) -> Mentor:
    """Update mentor profile"""
    mentor = get_mentor_by_id(db, mentor_id)
    if not mentor:
        raise MentorNotFoundError(mentor_id)
    
    # Update fields
    update_data = mentor_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(mentor, field, value)
    
    mentor.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(mentor)
    
    return mentor

def get_all_mentors(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    filters: Optional[Dict[str, Any]] = None
) -> List[Mentor]:
    """Get all mentors with filters"""
    query = db.query(Mentor)
    
    if filters:
        if "is_available" in filters:
            query = query.filter(Mentor.is_available == filters["is_available"])
        if "expertise_area" in filters:
            # Filter by expertise area (assuming it's stored as a list)
            query = query.filter(Mentor.expertise_areas.contains([filters["expertise_area"]]))
        if "department" in filters:
            query = query.filter(Mentor.department == filters["department"])
    
    return query.offset(skip).limit(limit).all()

def count_mentors(db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
    """Count mentors with filters"""
    query = db.query(func.count(Mentor.id))
    
    if filters:
        if "is_available" in filters:
            query = query.filter(Mentor.is_available == filters["is_available"])
    
    return query.scalar()

def assign_intern_to_mentor(db: Session, mentor_id: int, intern_id: int) -> Dict[str, Any]:
    """Assign intern to mentor"""
    mentor = get_mentor_by_id(db, mentor_id)
    if not mentor:
        raise MentorNotFoundError(mentor_id)
    
    # Check mentor capacity
    current_interns = db.query(Intern).filter(Intern.assigned_mentor_id == mentor_id).count()
    if current_interns >= mentor.max_interns:
        raise MentorCapacityExceededError(mentor_id, current_interns, mentor.max_interns)
    
    # Assign intern
    from app.services.intern_service import assign_mentor_to_intern
    intern = assign_mentor_to_intern(db, intern_id, mentor_id)
    
    # Update mentor stats
    mentor.current_interns_count = current_interns + 1
    mentor.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "mentor_id": mentor_id,
        "intern_id": intern_id,
        "assignment_date": datetime.utcnow(),
        "mentor_capacity": f"{mentor.current_interns_count}/{mentor.max_interns}"
    }

def get_mentor_interns(db: Session, mentor_id: int) -> List[Intern]:
    """Get all interns assigned to mentor"""
    return db.query(Intern).filter(Intern.assigned_mentor_id == mentor_id).all()

def submit_mentor_feedback(db: Session, mentor_id: int, feedback_data: MentorFeedback) -> Feedback:
    """Submit feedback from mentor to intern"""
    db_feedback = Feedback(
        mentor_id=mentor_id,
        intern_id=feedback_data.intern_id,
        task_id=feedback_data.task_id if hasattr(feedback_data, 'task_id') else None,
        feedback_type=feedback_data.feedback_type,
        title=feedback_data.title,
        content=feedback_data.content,
        rating=feedback_data.rating
    )
    
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    
    return db_feedback

def get_mentor_statistics(db: Session, mentor_id: int) -> Dict[str, Any]:
    """Get mentor statistics"""
    mentor = get_mentor_by_id(db, mentor_id)
    if not mentor:
        raise MentorNotFoundError(mentor_id)
    
    # Current interns
    current_interns = db.query(Intern).filter(
        and_(Intern.assigned_mentor_id == mentor_id, Intern.status == "active")
    ).count()
    
    # Total mentored
    total_mentored = db.query(Intern).filter(Intern.assigned_mentor_id == mentor_id).count()
    
    # Completed interns
    completed_interns = db.query(Intern).filter(
        and_(Intern.assigned_mentor_id == mentor_id, Intern.status == "completed")
    ).count()
    
    # Average intern performance
    avg_performance = db.query(func.avg(Intern.performance_score)).filter(
        and_(
            Intern.assigned_mentor_id == mentor_id,
            Intern.performance_score.isnot(None)
        )
    ).scalar() or 0.0
    
    # Feedback given
    feedback_count = db.query(Feedback).filter(Feedback.mentor_id == mentor_id).count()
    
    return {
        "current_interns": current_interns,
        "total_mentored": total_mentored,
        "completed_interns": completed_interns,
        "completion_rate": (completed_interns / total_mentored * 100) if total_mentored > 0 else 0,
        "average_intern_performance": round(avg_performance, 2),
        "capacity_utilization": (current_interns / mentor.max_interns * 100) if mentor.max_interns > 0 else 0,
        "feedback_given": feedback_count
    }

def get_mentor_dashboard_data(db: Session, mentor_id: int) -> Dict[str, Any]:
    """Get mentor dashboard data"""
    mentor = get_mentor_by_id(db, mentor_id)
    if not mentor:
        raise MentorNotFoundError(mentor_id)
    
    # Get assigned interns
    interns = get_mentor_interns(db, mentor_id)
    
    # Get recent tasks
    from app.models.task import Task
    recent_tasks = db.query(Task).filter(
        Task.created_by_mentor_id == mentor_id
    ).order_by(Task.created_at.desc()).limit(10).all()
    
    # Get pending submissions
    pending_submissions = db.query(Task).filter(
        and_(
            Task.created_by_mentor_id == mentor_id,
            Task.status == "submitted"
        )
    ).all()
    
    # Get statistics
    stats = get_mentor_statistics(db, mentor_id)
    
    return {
        "mentor_info": {
            "name": f"{mentor.user.first_name} {mentor.user.last_name}",
            "designation": mentor.designation,
            "department": mentor.department,
            "expertise_areas": mentor.expertise_areas
        },
        "assigned_interns": [
            {
                "id": intern.id,
                "name": f"{intern.user.first_name} {intern.user.last_name}",
                "program_track": intern.program_track,
                "status": intern.status,
                "performance_score": intern.performance_score
            }
            for intern in interns
        ],
        "recent_tasks": [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "due_date": task.due_date,
                "assigned_intern": task.assigned_intern.user.first_name + " " + task.assigned_intern.user.last_name if task.assigned_intern else None
            }
            for task in recent_tasks
        ],
        "pending_submissions": len(pending_submissions),
        "statistics": stats
    }

def calculate_mentor_performance_metrics(db: Session, mentor_id: int) -> Dict[str, Any]:
    """Calculate mentor performance metrics"""
    mentor = get_mentor_by_id(db, mentor_id)
    if not mentor:
        raise MentorNotFoundError(mentor_id)
    
    # Response time calculation (mock - would need actual response time tracking)
    avg_response_time = 24  # hours - placeholder
    
    # Feedback quality score (based on intern ratings)
    feedback_quality = db.query(func.avg(Feedback.rating)).filter(
        and_(Feedback.mentor_id == mentor_id, Feedback.rating.isnot(None))
    ).scalar() or 0.0
    
    # Success rate (interns who completed successfully)
    total_interns = db.query(Intern).filter(Intern.assigned_mentor_id == mentor_id).count()
    successful_interns = db.query(Intern).filter(
        and_(
            Intern.assigned_mentor_id == mentor_id,
            Intern.status == "completed",
            Intern.performance_score >= 70
        )
    ).count()
    
    success_rate = (successful_interns / total_interns * 100) if total_interns > 0 else 0
    
    return {
        "response_time_hours": avg_response_time,
        "feedback_quality_score": round(feedback_quality, 2),
        "success_rate": round(success_rate, 2),
        "total_interns_mentored": total_interns,
        "successful_completions": successful_interns,
        "current_capacity_usage": mentor.current_interns_count,
        "max_capacity": mentor.max_interns
    }

def get_available_mentors(db: Session, expertise_area: Optional[str] = None) -> List[Mentor]:
    """Get available mentors with capacity"""
    query = db.query(Mentor).filter(
        and_(
            Mentor.is_available == True,
            Mentor.current_interns_count < Mentor.max_interns
        )
    )
    
    if expertise_area:
        query = query.filter(Mentor.expertise_areas.contains([expertise_area]))
    
    return query.all()

def get_mentor_feedback_history(db: Session, mentor_id: int, limit: int = 50) -> List[Feedback]:
    """Get mentor's feedback history"""
    return db.query(Feedback).filter(
        Feedback.mentor_id == mentor_id
    ).order_by(Feedback.created_at.desc()).limit(limit).all()
