from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.task import Task, TaskStatus
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TaskSubmission,
    TaskList
)
from app.services.task_service import (
    create_task,
    get_task_by_id,
    get_tasks_by_intern,
    get_tasks_by_mentor,
    update_task,
    submit_task,
    evaluate_task_submission
)
from app.services.ai_service import auto_grade_submission
from app.api.deps import get_current_active_user, get_mentor_user

router = APIRouter()

@router.post("/", response_model=TaskResponse)
async def create_new_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Create new task (mentors only)"""
    task = create_task(
        db=db,
        task=task_data,
        created_by_mentor_id=current_user.mentor_profile.id
    )
    
    # Trigger AI-based task customization if needed
    await customize_task_for_intern(task)
    
    return task

@router.get("/my-tasks", response_model=TaskList)
async def get_my_tasks(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get tasks for current user"""
    if current_user.role.value == "intern":
        if not current_user.intern_profile:
            raise HTTPException(
                status_code=404,
                detail="Intern profile not found"
            )
        
        filters = {"status": status} if status else {}
        tasks = get_tasks_by_intern(
            db,
            intern_id=current_user.intern_profile.id,
            skip=skip,
            limit=limit,
            filters=filters
        )
    
    elif current_user.role.value == "mentor":
        if not current_user.mentor_profile:
            raise HTTPException(
                status_code=404,
                detail="Mentor profile not found"
            )
        
        tasks = get_tasks_by_mentor(
            db,
            mentor_id=current_user.mentor_profile.id,
            skip=skip,
            limit=limit
        )
    
    else:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )
    
    return {
        "tasks": tasks,
        "total": len(tasks),
        "skip": skip,
        "limit": limit
    }

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_details(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get task details"""
    task = get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
    
    # Check permissions
    can_access = False
    if current_user.role.value == "intern":
        can_access = (task.assigned_intern_id == current_user.intern_profile.id)
    elif current_user.role.value == "mentor":
        can_access = (task.created_by_mentor_id == current_user.mentor_profile.id)
    elif current_user.role.value in ["admin", "hr"]:
        can_access = True
    
    if not can_access:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )
    
    return task

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task_details(
    task_id: int,
    task_update: TaskUpdate,
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Update task (mentors only)"""
    task = get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
    
    # Check if mentor owns this task
    if task.created_by_mentor_id != current_user.mentor_profile.id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own tasks"
        )
    
    updated_task = update_task(db=db, task_id=task_id, task_update=task_update)
    return updated_task

@router.post("/{task_id}/submit")
async def submit_task_solution(
    task_id: int,
    submission_text: str,
    files: List[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Submit task solution"""
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Only interns can submit tasks"
        )
    
    task = get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
    
    if task.assigned_intern_id != current_user.intern_profile.id:
        raise HTTPException(
            status_code=403,
            detail="You can only submit your own tasks"
        )
    
    # Process file uploads
    file_urls = []
    if files:
        file_urls = await upload_task_files(files, task_id)
    
    # Submit task
    submission_data = TaskSubmission(
        submission_text=submission_text,
        submission_files=file_urls
    )
    
    submitted_task = submit_task(db=db, task_id=task_id, submission=submission_data)
    
    # Trigger AI auto-grading
    if task.auto_graded:
        ai_evaluation = await auto_grade_submission(submitted_task)
        evaluate_task_submission(
            db=db,
            task_id=task_id,
            ai_evaluation=ai_evaluation
        )
    
    return {
        "message": "Task submitted successfully",
        "task": submitted_task,
        "files_uploaded": len(file_urls)
    }

@router.put("/{task_id}/evaluate")
async def evaluate_task(
    task_id: int,
    score: float,
    feedback: str,
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Evaluate submitted task (mentors only)"""
    task = get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
    
    if task.created_by_mentor_id != current_user.mentor_profile.id:
        raise HTTPException(
            status_code=403,
            detail="You can only evaluate your own tasks"
        )
    
    if task.status != TaskStatus.SUBMITTED.value:
        raise HTTPException(
            status_code=400,
            detail="Task must be submitted before evaluation"
        )
    
    # Validate score
    if not (0 <= score <= 100):
        raise HTTPException(
            status_code=400,
            detail="Score must be between 0 and 100"
        )
    
    evaluated_task = evaluate_task_submission(
        db=db,
        task_id=task_id,
        score=score,
        mentor_feedback=feedback
    )
    
    return {
        "message": "Task evaluated successfully",
        "task": evaluated_task
    }

@router.post("/{task_id}/start")
async def start_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark task as started"""
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=403,
            detail="Only interns can start tasks"
        )
    
    task = get_task_by_id(db, task_id)
    if not task or task.assigned_intern_id != current_user.intern_profile.id:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
    
    if task.status != TaskStatus.ASSIGNED.value:
        raise HTTPException(
            status_code=400,
            detail="Task already started or completed"
        )
    
    updated_task = update_task(
        db=db,
        task_id=task_id,
        task_update=TaskUpdate(
            status=TaskStatus.IN_PROGRESS.value,
            started_date=datetime.utcnow()
        )
    )
    
    return {
        "message": "Task started successfully",
        "task": updated_task
    }
