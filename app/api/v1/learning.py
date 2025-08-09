from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.learning import (
    LearningModule,
    LearningProgress,
    Quiz,
    QuizAttempt,
    Certificate
)
from app.schemas.learning import (
    LearningModuleCreate,
    LearningModuleResponse,
    LearningProgressResponse,
    QuizCreate,
    QuizResponse,
    QuizAttemptCreate,
    QuizAttemptResponse,
    CertificateResponse
)
from app.services.learning_service import (
    create_learning_module,
    get_learning_module,
    get_learning_modules,
    update_learning_progress,
    create_quiz,
    submit_quiz_attempt,
    generate_certificate,
    get_learning_path_for_intern
)
from app.services.ai_service import (
    generate_personalized_content,
    assess_learning_progress,
    recommend_next_modules
)
from app.api.deps import get_current_active_user, get_admin_user, get_mentor_user

router = APIRouter()

@router.get("/modules", response_model=List[LearningModuleResponse])
async def get_all_learning_modules(
    track: Optional[str] = None,
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all available learning modules"""
    filters = {}
    if track:
        filters["track"] = track
    if difficulty:
        filters["difficulty"] = difficulty
    
    modules = get_learning_modules(db, filters=filters)
    return modules

@router.get("/modules/{module_id}", response_model=LearningModuleResponse)
async def get_learning_module_details(
    module_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get specific learning module details"""
    module = get_learning_module(db, module_id)
    if not module:
        raise HTTPException(
            status_code=404,
            detail="Learning module not found"
        )
    
    # Check if user has access to this module
    if not check_module_access(db, current_user.id, module_id):
        raise HTTPException(
            status_code=403,
            detail="Access denied to this module"
        )
    
    return module

@router.post("/modules", response_model=LearningModuleResponse)
async def create_new_learning_module(
    module_data: LearningModuleCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Create new learning module (admin only)"""
    module = create_learning_module(db=db, module=module_data, created_by=current_user.id)
    return module

@router.get("/my-path", response_model=Dict[str, Any])
async def get_my_learning_path(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get personalized learning path for current user"""
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Learning paths are only available for interns"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    # Get personalized learning path
    learning_path = get_learning_path_for_intern(db, intern.id)
    
    # Get AI recommendations for next modules
    next_recommendations = await recommend_next_modules(intern)
    
    return {
        "current_path": learning_path,
        "progress_summary": {
            "completed_modules": count_completed_modules(db, intern.id),
            "total_modules": len(learning_path.get("modules", [])),
            "overall_progress": calculate_overall_progress(db, intern.id)
        },
        "next_recommendations": next_recommendations,
        "estimated_completion": calculate_estimated_completion(learning_path)
    }

@router.post("/modules/{module_id}/start")
async def start_learning_module(
    module_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Start a learning module"""
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Only interns can start learning modules"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    module = get_learning_module(db, module_id)
    if not module:
        raise HTTPException(
            status_code=404,
            detail="Learning module not found"
        )
    
    # Check prerequisites
    if not check_prerequisites_met(db, intern.id, module_id):
        raise HTTPException(
            status_code=400,
            detail="Prerequisites not met for this module"
        )
    
    # Start the module
    progress = start_module_progress(db, intern.id, module_id)
    
    # Generate personalized content if needed
    personalized_content = await generate_personalized_content(module, intern)
    
    return {
        "message": "Module started successfully",
        "progress": progress,
        "personalized_content": personalized_content,
        "estimated_duration": module.estimated_duration
    }

@router.put("/modules/{module_id}/progress")
async def update_module_progress(
    module_id: int,
    progress_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update learning module progress"""
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Only interns can update progress"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    # Update progress
    updated_progress = update_learning_progress(
        db=db,
        intern_id=intern.id,
        module_id=module_id,
        progress_data=progress_data
    )
    
    # AI assessment of learning progress
    ai_assessment = await assess_learning_progress(updated_progress)
    
    return {
        "message": "Progress updated successfully",
        "progress": updated_progress,
        "ai_insights": ai_assessment,
        "next_steps": ai_assessment.get("recommendations", [])
    }

@router.post("/modules/{module_id}/complete")
async def complete_learning_module(
    module_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark learning module as completed"""
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Only interns can complete modules"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    # Check if module can be completed
    progress = get_module_progress(db, intern.id, module_id)
    if not progress or progress.completion_percentage < 100:
        raise HTTPException(
            status_code=400,
            detail="Module not fully completed yet"
        )
    
    # Complete the module
    completed_progress = complete_module(db, intern.id, module_id)
    
    # Check if certificate should be generated
    certificate = None
    if should_generate_certificate(db, intern.id, module_id):
        certificate = generate_certificate(db, intern.id, module_id)
    
    # Update overall intern progress
    update_intern_overall_progress(db, intern.id)
    
    return {
        "message": "Module completed successfully",
        "progress": completed_progress,
        "certificate": certificate,
        "unlocked_modules": get_newly_unlocked_modules(db, intern.id)
    }

@router.get("/quizzes/{quiz_id}", response_model=QuizResponse)
async def get_quiz_details(
    quiz_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get quiz details"""
    quiz = get_quiz_by_id(db, quiz_id)
    if not quiz:
        raise HTTPException(
            status_code=404,
            detail="Quiz not found"
        )
    
    # Check access permissions
    if not check_quiz_access(db, current_user.id, quiz_id):
        raise HTTPException(
            status_code=403,
            detail="Access denied to this quiz"
        )
    
    return quiz

@router.post("/quizzes/{quiz_id}/attempt")
async def submit_quiz_attempt(
    quiz_id: int,
    attempt_data: QuizAttemptCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Submit quiz attempt"""
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Only interns can take quizzes"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    quiz = get_quiz_by_id(db, quiz_id)
    if not quiz:
        raise HTTPException(
            status_code=404,
            detail="Quiz not found"
        )
    
    # Submit attempt
    attempt = submit_quiz_attempt(
        db=db,
        quiz_id=quiz_id,
        intern_id=intern.id,
        attempt_data=attempt_data
    )
    
    # AI evaluation of answers
    ai_evaluation = await evaluate_quiz_answers(attempt)
    
    # Update attempt with AI evaluation
    update_quiz_attempt_evaluation(db, attempt.id, ai_evaluation)
    
    return {
        "message": "Quiz submitted successfully",
        "attempt": attempt,
        "score": ai_evaluation.get("score"),
        "feedback": ai_evaluation.get("feedback"),
        "passed": ai_evaluation.get("score", 0) >= quiz.passing_score
    }

@router.get("/progress", response_model=LearningProgressResponse)
async def get_my_learning_progress(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's learning progress"""
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Learning progress is only available for interns"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    progress = get_comprehensive_learning_progress(db, intern.id)
    
    return {
        "overall_progress": progress.get("overall_percentage", 0),
        "modules_completed": progress.get("completed_modules", 0),
        "total_modules": progress.get("total_modules", 0),
        "time_spent": progress.get("total_time_spent", 0),
        "certificates_earned": progress.get("certificates", []),
        "current_streak": progress.get("learning_streak", 0),
        "skill_improvements": progress.get("skill_progress", {}),
        "recent_activities": progress.get("recent_activities", [])
    }

@router.get("/certificates", response_model=List[CertificateResponse])
async def get_my_certificates(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's earned certificates"""
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Certificates are only available for interns"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    certificates = get_intern_certificates(db, intern.id)
    return certificates

@router.get("/recommendations")
async def get_learning_recommendations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI-powered learning recommendations"""
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Recommendations are only available for interns"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    # Get AI recommendations
    recommendations = await generate_learning_recommendations(intern)
    
    return {
        "next_modules": recommendations.get("next_modules", []),
        "skill_gaps": recommendations.get("skill_gaps", []),
        "suggested_projects": recommendations.get("projects", []),
        "study_plan": recommendations.get("study_plan", {}),
        "estimated_timeline": recommendations.get("timeline", "")
    }

@router.post("/feedback")
async def submit_learning_feedback(
    module_id: int,
    rating: int,
    feedback_text: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Submit feedback for learning module"""
    if not (1 <= rating <= 5):
        raise HTTPException(
            status_code=400,
            detail="Rating must be between 1 and 5"
        )
    
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Only interns can submit learning feedback"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    feedback = submit_module_feedback(
        db=db,
        intern_id=intern.id,
        module_id=module_id,
        rating=rating,
        feedback_text=feedback_text
    )
    
    return {
        "message": "Feedback submitted successfully",
        "feedback": feedback
    }
