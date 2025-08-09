from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime
from fastapi import UploadFile

from app.core.exceptions import InternNotFoundError, ValidationError, NotFoundError
from app.models.intern import Intern
from app.models.user import User
from app.schemas.intern import InternCreate, InternUpdate
from app.utils.file_handler import file_handler
from app.services.ai_service import analyze_resume_ai, assess_skills_ai

def create_intern_profile(db: Session, intern: InternCreate, user_id: int) -> Intern:
    """Create intern profile"""
    # Generate intern ID
    year = datetime.now().year
    count = db.query(Intern).count() + 1
    intern_id = f"INT-{year}-{count:04d}"
    
    db_intern = Intern(
        intern_id=intern_id,
        user_id=user_id,
        university=intern.university,
        degree=intern.degree,
        graduation_year=intern.graduation_year,
        major=intern.major,
        gpa=intern.gpa,
        program_track=intern.program_track,
        experience_level=intern.experience_level,
        skills=intern.skills,
        previous_experience=intern.previous_experience,
        portfolio_url=intern.portfolio_url,
        linkedin_url=intern.linkedin_url,
        github_url=intern.github_url,
        status="pending"
    )
    
    db.add(db_intern)
    db.commit()
    db.refresh(db_intern)
    
    return db_intern

def get_intern_by_id(db: Session, intern_id: int) -> Optional[Intern]:
    """Get intern by ID"""
    return db.query(Intern).filter(Intern.id == intern_id).first()

def get_intern_by_user_id(db: Session, user_id: int) -> Optional[Intern]:
    """Get intern by user ID"""
    return db.query(Intern).filter(Intern.user_id == user_id).first()

def update_intern_profile(db: Session, intern_id: int, intern_update: InternUpdate) -> Intern:
    """Update intern profile"""
    intern = get_intern_by_id(db, intern_id)
    if not intern:
        raise InternNotFoundError(intern_id)
    
    # Update fields
    update_data = intern_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(intern, field, value)
    
    intern.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(intern)
    
    return intern

def get_all_interns(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    filters: Optional[Dict[str, Any]] = None
) -> List[Intern]:
    """Get all interns with filters"""
    query = db.query(Intern)
    
    if filters:
        if "status" in filters:
            query = query.filter(Intern.status == filters["status"])
        if "program_track" in filters:
            query = query.filter(Intern.program_track == filters["program_track"])
        if "experience_level" in filters:
            query = query.filter(Intern.experience_level == filters["experience_level"])
        if "university" in filters:
            query = query.filter(Intern.university.ilike(f"%{filters['university']}%"))
        if "has_mentor" in filters:
            if filters["has_mentor"]:
                query = query.filter(Intern.assigned_mentor_id.isnot(None))
            else:
                query = query.filter(Intern.assigned_mentor_id.is_(None))
    
    return query.offset(skip).limit(limit).all()

def count_interns(db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
    """Count interns with filters"""
    query = db.query(func.count(Intern.id))
    
    if filters:
        if "status" in filters:
            query = query.filter(Intern.status == filters["status"])
        if "program_track" in filters:
            query = query.filter(Intern.program_track == filters["program_track"])
    
    return query.scalar()

async def upload_resume(file: UploadFile, intern_id: int) -> str:
    """Upload intern resume"""
    try:
        file_url = await file_handler.upload_resume(file, intern_id)
        return file_url
    except Exception as e:
        raise ValidationError(f"Failed to upload resume: {str(e)}")

async def analyze_resume(file: UploadFile) -> Dict[str, Any]:
    """Analyze resume using AI"""
    try:
        # Read file content
        content = await file.read()
        
        # Use AI service to analyze
        analysis = await analyze_resume_ai(content, file.filename)
        
        return analysis
    except Exception as e:
        raise ValidationError(f"Failed to analyze resume: {str(e)}")

async def assess_skills(intern: Intern) -> Dict[str, Any]:
    """Assess intern skills using AI"""
    try:
        intern_data = {
            "skills": intern.skills or [],
            "experience_level": intern.experience_level,
            "education": {
                "university": intern.university,
                "degree": intern.degree,
                "major": intern.major,
                "gpa": intern.gpa
            },
            "experience": intern.previous_experience or "",
            "projects": []  # Could be extracted from portfolio
        }
        
        assessment = await assess_skills_ai(intern_data)
        
        return assessment
    except Exception as e:
        raise ValidationError(f"Failed to assess skills: {str(e)}")

def get_intern_statistics(db: Session) -> Dict[str, Any]:
    """Get intern statistics"""
    total_interns = db.query(Intern).count()
    active_interns = db.query(Intern).filter(Intern.status == "active").count()
    completed_interns = db.query(Intern).filter(Intern.status == "completed").count()
    pending_interns = db.query(Intern).filter(Intern.status == "pending").count()
    
    # Calculate average performance
    avg_performance = db.query(func.avg(Intern.performance_score)).filter(
        Intern.performance_score.isnot(None)
    ).scalar() or 0.0
    
    # Calculate completion rate
    completion_rate = (completed_interns / total_interns * 100) if total_interns > 0 else 0
    
    return {
        "total_interns": total_interns,
        "active_interns": active_interns,
        "completed_interns": completed_interns,
        "pending_interns": pending_interns,
        "average_performance": round(avg_performance, 2),
        "completion_rate": round(completion_rate, 2)
    }

def get_intern_by_intern_id(db: Session, intern_id: str) -> Optional[Intern]:
    """Get intern by intern_id string"""
    return db.query(Intern).filter(Intern.intern_id == intern_id).first()

def search_interns(
    db: Session, 
    search_term: str, 
    skip: int = 0, 
    limit: int = 100
) -> List[Intern]:
    """Search interns by name, skills, or university"""
    return db.query(Intern).join(User).filter(
        or_(
            User.first_name.ilike(f"%{search_term}%"),
            User.last_name.ilike(f"%{search_term}%"),
            Intern.university.ilike(f"%{search_term}%"),
            Intern.major.ilike(f"%{search_term}%")
        )
    ).offset(skip).limit(limit).all()

def update_intern_performance(db: Session, intern_id: int, performance_score: float):
    """Update intern performance score"""
    intern = get_intern_by_id(db, intern_id)
    if not intern:
        raise InternNotFoundError(intern_id)
    
    intern.performance_score = performance_score
    intern.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(intern)
    
    return intern

def get_intern_progress_summary(db: Session, intern_id: int) -> Dict[str, Any]:
    """Get comprehensive intern progress summary"""
    intern = get_intern_by_id(db, intern_id)
    if not intern:
        raise InternNotFoundError(intern_id)
    
    # Get task progress
    from app.models.task import Task
    total_tasks = db.query(Task).filter(Task.assigned_intern_id == intern_id).count()
    completed_tasks = db.query(Task).filter(
        and_(Task.assigned_intern_id == intern_id, Task.status == "completed")
    ).count()
    
    # Get learning progress
    from app.models.learning import LearningProgress
    learning_modules = db.query(LearningProgress).filter(
        LearningProgress.intern_id == intern_id
    ).count()
    completed_modules = db.query(LearningProgress).filter(
        and_(
            LearningProgress.intern_id == intern_id,
            LearningProgress.status == "completed"
        )
    ).count()
    
    return {
        "intern_info": {
            "id": intern.id,
            "intern_id": intern.intern_id,
            "name": f"{intern.user.first_name} {intern.user.last_name}",
            "program_track": intern.program_track,
            "status": intern.status
        },
        "task_progress": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        },
        "learning_progress": {
            "total_modules": learning_modules,
            "completed_modules": completed_modules,
            "completion_rate": (completed_modules / learning_modules * 100) if learning_modules > 0 else 0
        },
        "overall_performance": intern.performance_score,
        "last_updated": intern.updated_at
    }

def get_interns_by_mentor(db: Session, mentor_id: int) -> List[Intern]:
    """Get all interns assigned to a mentor"""
    return db.query(Intern).filter(Intern.assigned_mentor_id == mentor_id).all()

def assign_mentor_to_intern(db: Session, intern_id: int, mentor_id: int) -> Intern:
    """Assign mentor to intern"""
    intern = get_intern_by_id(db, intern_id)
    if not intern:
        raise InternNotFoundError(intern_id)
    
    intern.assigned_mentor_id = mentor_id
    intern.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(intern)
    
    return intern

def update_intern_status(db: Session, intern_id: int, status: str) -> Intern:
    """Update intern status"""
    intern = get_intern_by_id(db, intern_id)
    if not intern:
        raise InternNotFoundError(intern_id)
    
    intern.status = status
    intern.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(intern)
    
    return intern
