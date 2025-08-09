from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime

from app.core.exceptions import TaskNotFoundError, InvalidTaskStatusError
from app.models.task import Task, TaskStatus
from app.models.intern import Intern
from app.schemas.task import TaskCreate, TaskUpdate, TaskSubmission

def create_task(db: Session, task: TaskCreate, created_by_mentor_id: int) -> Task:
    """Create new task"""
    db_task = Task(
        title=task.title,
        description=task.description,
        instructions=task.instructions,
        priority=task.priority,
        category=task.category,
        tags=task.tags,
        estimated_hours=task.estimated_hours,
        difficulty_level=task.difficulty_level,
        assigned_intern_id=task.assigned_intern_id,
        created_by_mentor_id=created_by_mentor_id,
        due_date=task.due_date,
        required_skills=task.required_skills,
        learning_objectives=task.learning_objectives,
        deliverables=task.deliverables,
        assigned_date=datetime.utcnow(),
        status=TaskStatus.ASSIGNED
    )
    
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    return db_task

def get_task_by_id(db: Session, task_id: int) -> Optional[Task]:
    """Get task by ID"""
    return db.query(Task).filter(Task.id == task_id).first()

def update_task(db: Session, task_id: int, task_update: TaskUpdate) -> Task:
    """Update task"""
    task = get_task_by_id(db, task_id)
    if not task:
        raise TaskNotFoundError(task_id)
    
    # Update fields
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    task.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(task)
    
    return task

def get_tasks_by_intern(
    db: Session, 
    intern_id: int, 
    skip: int = 0, 
    limit: int = 50, 
    filters: Optional[Dict[str, Any]] = None
) -> List[Task]:
    """Get tasks assigned to intern"""
    query = db.query(Task).filter(Task.assigned_intern_id == intern_id)
    
    if filters:
        if "status" in filters:
            query = query.filter(Task.status == filters["status"])
        if "priority" in filters:
            query = query.filter(Task.priority == filters["priority"])
        if "category" in filters:
            query = query.filter(Task.category == filters["category"])
        if "overdue_only" in filters and filters["overdue_only"]:
            query = query.filter(
                and_(
                    Task.due_date < datetime.utcnow(),
                    Task.status.notin_(["completed"])
                )
            )
    
    return query.order_by(Task.due_date.asc()).offset(skip).limit(limit).all()

def get_tasks_by_mentor(
    db: Session, 
    mentor_id: int, 
    skip: int = 0, 
    limit: int = 100
) -> List[Task]:
    """Get tasks created by mentor"""
    return db.query(Task).filter(
        Task.created_by_mentor_id == mentor_id
    ).order_by(Task.created_at.desc()).offset(skip).limit(limit).all()

def submit_task(db: Session, task_id: int, submission: TaskSubmission) -> Task:
    """Submit task solution"""
    task = get_task_by_id(db, task_id)
    if not task:
        raise TaskNotFoundError(task_id)
    
    if task.status not in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]:
        raise InvalidTaskStatusError(task.status.value, TaskStatus.SUBMITTED.value)
    
    # Update task with submission
    task.submission_text = submission.submission_text
    task.submission_files = submission.submission_files
    task.submission_date = datetime.utcnow()
    task.status = TaskStatus.SUBMITTED
    task.progress_percentage = 100.0
    task.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(task)
    
    return task

def evaluate_task_submission(
    db: Session, 
    task_id: int, 
    score: Optional[float] = None, 
    mentor_feedback: Optional[str] = None,
    ai_evaluation: Optional[Dict[str, Any]] = None
) -> Task:
    """Evaluate submitted task"""
    task = get_task_by_id(db, task_id)
    if not task:
        raise TaskNotFoundError(task_id)
    
    if task.status != TaskStatus.SUBMITTED:
        raise InvalidTaskStatusError(task.status.value, "evaluated")
    
    # Update task with evaluation
    if score is not None:
        task.score = score
    if mentor_feedback:
        task.mentor_feedback = mentor_feedback
    if ai_evaluation:
        task.ai_feedback = ai_evaluation
    
    task.status = TaskStatus.COMPLETED if (score or 0) >= 70 else TaskStatus.REVISION_REQUIRED
    task.completed_date = datetime.utcnow() if task.status == TaskStatus.COMPLETED else None
    task.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(task)
    
    return task

def get_overdue_tasks(db: Session) -> List[Task]:
    """Get all overdue tasks"""
    return db.query(Task).filter(
        and_(
            Task.due_date < datetime.utcnow(),
            Task.status.notin_([TaskStatus.COMPLETED])
        )
    ).all()

def get_task_statistics(db: Session) -> Dict[str, Any]:
    """Get task statistics"""
    total_tasks = db.query(Task).count()
    completed_tasks = db.query(Task).filter(Task.status == TaskStatus.COMPLETED).count()
    in_progress_tasks = db.query(Task).filter(Task.status == TaskStatus.IN_PROGRESS).count()
    overdue_tasks = len(get_overdue_tasks(db))
    
    # Average completion time
    avg_completion_time = db.query(
        func.avg(
            func.extract('epoch', Task.completed_date - Task.assigned_date) / 3600
        )
    ).filter(
        and_(
            Task.status == TaskStatus.COMPLETED,
            Task.completed_date.isnot(None)
        )
    ).scalar() or 0.0
    
    # Average score
    avg_score = db.query(func.avg(Task.score)).filter(
        Task.score.isnot(None)
    ).scalar() or 0.0
    
    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "in_progress_tasks": in_progress_tasks,
        "overdue_tasks": overdue_tasks,
        "completion_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
        "average_completion_time_hours": round(avg_completion_time, 2),
        "average_score": round(avg_score, 2)
    }

def get_tasks_requiring_review(db: Session, mentor_id: Optional[int] = None) -> List[Task]:
    """Get tasks that need mentor review"""
    query = db.query(Task).filter(Task.status == TaskStatus.SUBMITTED)
    
    if mentor_id:
        query = query.filter(Task.created_by_mentor_id == mentor_id)
    
    return query.order_by(Task.submission_date.asc()).all()

def mark_task_as_started(db: Session, task_id: int) -> Task:
    """Mark task as started"""
    task = get_task_by_id(db, task_id)
    if not task:
        raise TaskNotFoundError(task_id)
    
    if task.status != TaskStatus.ASSIGNED:
        raise InvalidTaskStatusError(task.status.value, TaskStatus.IN_PROGRESS.value)
    
    task.status = TaskStatus.IN_PROGRESS
    task.started_date = datetime.utcnow()
    task.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(task)
    
    return task

def update_task_progress(db: Session, task_id: int, progress_percentage: float) -> Task:
    """Update task progress percentage"""
    task = get_task_by_id(db, task_id)
    if not task:
        raise TaskNotFoundError(task_id)
    
    task.progress_percentage = max(0, min(100, progress_percentage))
    task.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(task)
    
    return task

def search_tasks(
    db: Session, 
    search_term: str, 
    skip: int = 0, 
    limit: int = 100
) -> List[Task]:
    """Search tasks by title or description"""
    return db.query(Task).filter(
        or_(
            Task.title.ilike(f"%{search_term}%"),
            Task.description.ilike(f"%{search_term}%")
        )
    ).offset(skip).limit(limit).all()

def get_tasks_by_category(db: Session, category: str) -> List[Task]:
    """Get tasks by category"""
    return db.query(Task).filter(Task.category == category).all()

def get_intern_task_summary(db: Session, intern_id: int) -> Dict[str, Any]:
    """Get task summary for intern"""
    total_tasks = db.query(Task).filter(Task.assigned_intern_id == intern_id).count()
    completed_tasks = db.query(Task).filter(
        and_(Task.assigned_intern_id == intern_id, Task.status == TaskStatus.COMPLETED)
    ).count()
    in_progress_tasks = db.query(Task).filter(
        and_(Task.assigned_intern_id == intern_id, Task.status == TaskStatus.IN_PROGRESS)
    ).count()
    
    # Average score
    avg_score = db.query(func.avg(Task.score)).filter(
        and_(Task.assigned_intern_id == intern_id, Task.score.isnot(None))
    ).scalar() or 0.0
    
    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "in_progress_tasks": in_progress_tasks,
        "completion_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
        "average_score": round(avg_score, 2)
    }

async def upload_task_files(files: List[UploadFile], task_id: int) -> List[str]:
    """Upload task submission files"""
    try:
        from app.utils.file_handler import file_handler
        file_urls = await file_handler.upload_task_files(files, task_id)
        return file_urls
    except Exception as e:
        raise ValidationError(f"Failed to upload task files: {str(e)}")

def get_user_id_for_intern(db: Session, intern_id: int) -> Optional[int]:
    """Get user ID for intern"""
    intern = db.query(Intern).filter(Intern.id == intern_id).first()
    return intern.user_id if intern else None

def get_user_id_for_mentor(db: Session, mentor_id: int) -> Optional[int]:
    """Get user ID for mentor"""
    from app.models.mentor import Mentor
    mentor = db.query(Mentor).filter(Mentor.id == mentor_id).first()
    return mentor.user_id if mentor else None

def can_user_update_task(user_id: int, task: Task, db: Session) -> bool:
    """Check if user can update task"""
    # Intern can update their own tasks
    if task.assigned_intern:
        if task.assigned_intern.user_id == user_id:
            return True
    
    # Mentor can update tasks they created
    if task.created_by_mentor:
        if task.created_by_mentor.user_id == user_id:
            return True
    
    return False
