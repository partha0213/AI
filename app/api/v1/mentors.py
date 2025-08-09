from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.mentor import Mentor
from app.models.intern import Intern
from app.schemas.mentor import (
    MentorCreate,
    MentorResponse,
    MentorUpdate,
    MentorList,
    MentorshipRequest,
    MentorFeedback
)
from app.services.mentor_service import (
    create_mentor_profile,
    get_mentor_by_id,
    get_mentor_by_user_id,
    update_mentor_profile,
    get_all_mentors,
    assign_intern_to_mentor,
    get_mentor_interns,
    submit_mentor_feedback
)
from app.services.notification_service import send_mentorship_notification
from app.api.deps import get_current_active_user, get_admin_user, get_mentor_user

router = APIRouter()

@router.post("/profile", response_model=MentorResponse)
async def create_mentor_profile(
    mentor_data: MentorCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create mentor profile"""
    if current_user.role not in [UserRole.MENTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only mentors can create mentor profiles"
        )
    
    # Check if profile already exists
    existing_profile = get_mentor_by_user_id(db, current_user.id)
    if existing_profile:
        raise HTTPException(
            status_code=400,
            detail="Mentor profile already exists"
        )
    
    mentor = create_mentor_profile(db=db, mentor=mentor_data, user_id=current_user.id)
    return mentor

@router.get("/profile", response_model=MentorResponse)
async def get_my_mentor_profile(
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Get current mentor's profile"""
    mentor = get_mentor_by_user_id(db, current_user.id)
    if not mentor:
        raise HTTPException(
            status_code=404,
            detail="Mentor profile not found"
        )
    return mentor

@router.put("/profile", response_model=MentorResponse)
async def update_my_mentor_profile(
    mentor_update: MentorUpdate,
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Update current mentor's profile"""
    mentor = get_mentor_by_user_id(db, current_user.id)
    if not mentor:
        raise HTTPException(
            status_code=404,
            detail="Mentor profile not found"
        )
    
    updated_mentor = update_mentor_profile(
        db=db, 
        mentor_id=mentor.id, 
        mentor_update=mentor_update
    )
    return updated_mentor

@router.get("/", response_model=MentorList)
async def get_all_mentors_list(
    skip: int = 0,
    limit: int = 100,
    expertise_area: Optional[str] = None,
    available_only: bool = True,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get all mentors (admin only)"""
    filters = {}
    if expertise_area:
        filters["expertise_area"] = expertise_area
    if available_only:
        filters["is_available"] = True
    
    mentors = get_all_mentors(db, skip=skip, limit=limit, filters=filters)
    total = count_mentors(db, filters=filters)
    
    return {
        "mentors": mentors,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/my-interns", response_model=List[Dict])
async def get_my_assigned_interns(
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Get interns assigned to current mentor"""
    mentor = get_mentor_by_user_id(db, current_user.id)
    if not mentor:
        raise HTTPException(
            status_code=404,
            detail="Mentor profile not found"
        )
    
    interns = get_mentor_interns(db, mentor.id)
    
    # Format response with additional info
    intern_details = []
    for intern in interns:
        intern_info = {
            "intern": intern,
            "progress": {
                "completed_tasks": intern.completed_tasks,
                "total_tasks": intern.total_tasks,
                "performance_score": intern.performance_score
            },
            "recent_activity": get_intern_recent_activity(db, intern.id)
        }
        intern_details.append(intern_info)
    
    return intern_details

@router.post("/assign-intern")
async def assign_intern(
    mentorship_request: MentorshipRequest,
    current_user: User = Depends(get_admin_user),
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Assign intern to mentor (admin only)"""
    mentor = get_mentor_by_id(db, mentorship_request.mentor_id)
    if not mentor:
        raise HTTPException(
            status_code=404,
            detail="Mentor not found"
        )
    
    intern = get_intern_by_id(db, mentorship_request.intern_id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern not found"
        )
    
    # Check mentor capacity
    if mentor.current_interns_count >= mentor.max_interns:
        raise HTTPException(
            status_code=400,
            detail="Mentor has reached maximum intern capacity"
        )
    
    # Assign intern to mentor
    assignment_result = assign_intern_to_mentor(
        db=db,
        mentor_id=mentor.id,
        intern_id=intern.id
    )
    
    # Send notifications
    background_tasks.add_task(
        send_mentorship_notification,
        mentor.user.email,
        intern.user.email,
        "assignment"
    )
    
    return {
        "message": "Intern assigned to mentor successfully",
        "assignment": assignment_result
    }

@router.post("/feedback")
async def submit_feedback(
    feedback_data: MentorFeedback,
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Submit feedback for intern"""
    mentor = get_mentor_by_user_id(db, current_user.id)
    if not mentor:
        raise HTTPException(
            status_code=404,
            detail="Mentor profile not found"
        )
    
    # Verify intern is assigned to this mentor
    intern = get_intern_by_id(db, feedback_data.intern_id)
    if not intern or intern.assigned_mentor_id != mentor.id:
        raise HTTPException(
            status_code=403,
            detail="You can only provide feedback for your assigned interns"
        )
    
    feedback = submit_mentor_feedback(
        db=db,
        mentor_id=mentor.id,
        feedback_data=feedback_data
    )
    
    return {
        "message": "Feedback submitted successfully",
        "feedback": feedback
    }

@router.get("/analytics/dashboard")
async def get_mentor_dashboard(
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Get mentor dashboard analytics"""
    mentor = get_mentor_by_user_id(db, current_user.id)
    if not mentor:
        raise HTTPException(
            status_code=404,
            detail="Mentor profile not found"
        )
    
    # Get dashboard metrics
    dashboard_data = {
        "mentor_info": {
            "name": f"{mentor.user.first_name} {mentor.user.last_name}",
            "designation": mentor.designation,
            "department": mentor.department,
            "expertise_areas": mentor.expertise_areas
        },
        "current_stats": {
            "active_interns": mentor.current_interns_count,
            "max_capacity": mentor.max_interns,
            "capacity_utilization": (mentor.current_interns_count / mentor.max_interns) * 100 if mentor.max_interns > 0 else 0,
            "total_mentored": mentor.total_interns_mentored,
            "average_rating": mentor.average_intern_rating
        },
        "recent_activities": get_mentor_recent_activities(db, mentor.id),
        "performance_metrics": {
            "response_time": mentor.feedback_response_time,
            "completion_rate": calculate_mentor_completion_rate(db, mentor.id),
            "satisfaction_score": calculate_mentor_satisfaction(db, mentor.id)
        },
        "upcoming_deadlines": get_mentor_upcoming_deadlines(db, mentor.id)
    }
    
    return dashboard_data

@router.put("/availability")
async def update_availability(
    is_available: bool,
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Update mentor availability status"""
    mentor = get_mentor_by_user_id(db, current_user.id)
    if not mentor:
        raise HTTPException(
            status_code=404,
            detail="Mentor profile not found"
        )
    
    updated_mentor = update_mentor_profile(
        db=db,
        mentor_id=mentor.id,
        mentor_update=MentorUpdate(is_available=is_available)
    )
    
    return {
        "message": f"Availability updated to {'available' if is_available else 'unavailable'}",
        "mentor": updated_mentor
    }

@router.get("/{mentor_id}/performance")
async def get_mentor_performance(
    mentor_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get detailed mentor performance metrics (admin only)"""
    mentor = get_mentor_by_id(db, mentor_id)
    if not mentor:
        raise HTTPException(
            status_code=404,
            detail="Mentor not found"
        )
    
    performance_data = {
        "mentor_info": {
            "id": mentor.id,
            "name": f"{mentor.user.first_name} {mentor.user.last_name}",
            "designation": mentor.designation,
            "experience": mentor.years_of_experience
        },
        "mentorship_stats": {
            "total_interns": mentor.total_interns_mentored,
            "current_interns": mentor.current_interns_count,
            "completion_rate": calculate_mentor_completion_rate(db, mentor.id),
            "average_intern_performance": calculate_average_intern_performance(db, mentor.id)
        },
        "feedback_metrics": {
            "response_time": mentor.feedback_response_time,
            "feedback_quality_score": calculate_feedback_quality(db, mentor.id),
            "total_feedback_given": count_mentor_feedback(db, mentor.id)
        },
        "intern_outcomes": {
            "successful_completions": count_successful_interns(db, mentor.id),
            "improvement_rate": calculate_intern_improvement_rate(db, mentor.id),
            "employment_rate": calculate_employment_rate(db, mentor.id)
        }
    }
    
    return performance_data
