from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.intern import Intern, InternStatus
from app.schemas.intern import (
    InternCreate,
    InternResponse,
    InternUpdate,
    InternProfileComplete,
    InternList
)
from app.services.intern_service import (
    create_intern_profile,
    get_intern_by_id,
    get_intern_by_user_id,
    update_intern_profile,
    get_all_interns,
    upload_resume
)
from app.services.ai_service import analyze_resume, assess_skills
from app.api.deps import get_current_active_user, get_admin_user, get_mentor_user

router = APIRouter()

@router.post("/profile", response_model=InternResponse)
async def create_profile(
    intern_data: InternCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create intern profile"""
    if current_user.role != UserRole.INTERN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only interns can create intern profiles"
        )
    
    # Check if profile already exists
    existing_profile = get_intern_by_user_id(db, current_user.id)
    if existing_profile:
        raise HTTPException(
            status_code=400,
            detail="Intern profile already exists"
        )
    
    intern = create_intern_profile(db=db, intern=intern_data, user_id=current_user.id)
    return intern

@router.get("/profile", response_model=InternResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current intern's profile"""
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    return intern

@router.put("/profile", response_model=InternResponse)
async def update_my_profile(
    intern_update: InternUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current intern's profile"""
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    updated_intern = update_intern_profile(db=db, intern_id=intern.id, intern_update=intern_update)
    return updated_intern

@router.post("/resume-upload")
async def upload_resume_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload and analyze resume"""
    if not file.filename.lower().endswith(('.pdf', '.doc', '.docx')):
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOC, and DOCX files are allowed"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    # Upload file to storage
    file_url = await upload_resume(file, intern.id)
    
    # Analyze resume with AI
    resume_analysis = await analyze_resume(file)
    
    # Update intern profile with extracted information
    update_data = {
        "skills": resume_analysis.get("skills", []),
        "experience_level": resume_analysis.get("experience_level"),
        "previous_experience": resume_analysis.get("experience_summary")
    }
    
    updated_intern = update_intern_profile(
        db=db, 
        intern_id=intern.id, 
        intern_update=InternUpdate(**update_data)
    )
    
    return {
        "message": "Resume uploaded and analyzed successfully",
        "file_url": file_url,
        "analysis": resume_analysis,
        "intern": updated_intern
    }

@router.get("/", response_model=InternList)
async def get_all_interns_list(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    program_track: Optional[str] = None,
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Get all interns (for mentors and admins)"""
    filters = {}
    if status:
        filters["status"] = status
    if program_track:
        filters["program_track"] = program_track
    
    interns = get_all_interns(db, skip=skip, limit=limit, filters=filters)
    total = count_interns(db, filters=filters)
    
    return {
        "interns": interns,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/{intern_id}", response_model=InternResponse)
async def get_intern_details(
    intern_id: int,
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Get intern details by ID (for mentors and admins)"""
    intern = get_intern_by_id(db, intern_id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern not found"
        )
    return intern

@router.put("/{intern_id}/status")
async def update_intern_status(
    intern_id: int,
    status: str = Form(...),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Update intern status (admin only)"""
    if status not in [s.value for s in InternStatus]:
        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )
    
    intern = get_intern_by_id(db, intern_id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern not found"
        )
    
    updated_intern = update_intern_profile(
        db=db,
        intern_id=intern_id,
        intern_update=InternUpdate(status=status)
    )
    
    return {
        "message": f"Intern status updated to {status}",
        "intern": updated_intern
    }

@router.post("/ai-assessment")
async def trigger_ai_assessment(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Trigger comprehensive AI assessment for intern"""
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    # Trigger AI assessment
    assessment_result = await assess_skills(intern)
    
    # Update intern profile with assessment results
    update_data = {
        "assessment_score": assessment_result.get("overall_score"),
        "skill_assessment": assessment_result.get("skill_breakdown"),
        "personality_traits": assessment_result.get("personality"),
        "learning_style": assessment_result.get("learning_style")
    }
    
    updated_intern = update_intern_profile(
        db=db,
        intern_id=intern.id,
        intern_update=InternUpdate(**update_data)
    )
    
    return {
        "message": "AI assessment completed",
        "assessment_result": assessment_result,
        "intern": updated_intern
    }
