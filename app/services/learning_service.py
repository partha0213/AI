from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.learning import (
    LearningModule,
    LearningProgress,
    Quiz,
    QuizAttempt,
    Certificate
)
from app.models.intern import Intern
from app.schemas.learning import (
    LearningModuleCreate,
    QuizCreate,
    QuizAttemptCreate
)
import uuid
from datetime import datetime

def create_learning_module(
    db: Session, 
    module: LearningModuleCreate, 
    created_by: int
) -> LearningModule:
    """Create new learning module"""
    db_module = LearningModule(
        title=module.title,
        description=module.description,
        content=module.content,
        module_type=module.module_type,
        track=module.track,
        category=module.category,
        tags=module.tags,
        difficulty=module.difficulty,
        prerequisites=module.prerequisites,
        learning_objectives=module.learning_objectives,
        estimated_duration=module.estimated_duration,
        video_url=module.video_url,
        materials=module.materials,
        created_by=created_by,
        order_index=module.order_index
    )
    
    db.add(db_module)
    db.commit()
    db.refresh(db_module)
    return db_module

def get_learning_module(db: Session, module_id: int) -> Optional[LearningModule]:
    """Get learning module by ID"""
    return db.query(LearningModule).filter(
        and_(
            LearningModule.id == module_id,
            LearningModule.is_active == True
        )
    ).first()

def get_learning_modules(
    db: Session, 
    filters: Dict[str, Any] = None,
    skip: int = 0,
    limit: int = 100
) -> List[LearningModule]:
    """Get learning modules with filters"""
    query = db.query(LearningModule).filter(LearningModule.is_active == True)
    
    if filters:
        if "track" in filters:
            query = query.filter(LearningModule.track == filters["track"])
        if "difficulty" in filters:
            query = query.filter(LearningModule.difficulty == filters["difficulty"])
        if "category" in filters:
            query = query.filter(LearningModule.category == filters["category"])
    
    return query.order_by(LearningModule.order_index).offset(skip).limit(limit).all()

def start_module_progress(
    db: Session, 
    intern_id: int, 
    module_id: int
) -> LearningProgress:
    """Start progress tracking for a module"""
    # Check if progress already exists
    existing_progress = db.query(LearningProgress).filter(
        and_(
            LearningProgress.intern_id == intern_id,
            LearningProgress.module_id == module_id
        )
    ).first()
    
    if existing_progress:
        # Update existing progress
        existing_progress.status = "in_progress"
        existing_progress.started_at = datetime.utcnow()
        existing_progress.last_accessed = datetime.utcnow()
        existing_progress.access_count += 1
        db.commit()
        db.refresh(existing_progress)
        return existing_progress
    
    # Create new progress record
    progress = LearningProgress(
        intern_id=intern_id,
        module_id=module_id,
        status="in_progress",
        started_at=datetime.utcnow(),
        last_accessed=datetime.utcnow(),
        access_count=1
    )
    
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress

def update_learning_progress(
    db: Session,
    intern_id: int,
    module_id: int,
    progress_data: Dict[str, Any]
) -> LearningProgress:
    """Update learning progress"""
    progress = db.query(LearningProgress).filter(
        and_(
            LearningProgress.intern_id == intern_id,
            LearningProgress.module_id == module_id
        )
    ).first()
    
    if not progress:
        # Create new progress if doesn't exist
        progress = start_module_progress(db, intern_id, module_id)
    
    # Update progress fields
    if "completion_percentage" in progress_data:
        progress.completion_percentage = progress_data["completion_percentage"]
    
    if "time_spent" in progress_data:
        progress.time_spent += progress_data["time_spent"]
    
    if "status" in progress_data:
        progress.status = progress_data["status"]
    
    progress.last_accessed = datetime.utcnow()
    progress.access_count += 1
    
    # Mark as completed if 100%
    if progress.completion_percentage >= 100 and progress.status != "completed":
        progress.status = "completed"
        progress.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(progress)
    return progress

def submit_quiz_attempt(
    db: Session,
    quiz_id: int,
    intern_id: int,
    attempt_data: QuizAttemptCreate
) -> QuizAttempt:
    """Submit quiz attempt"""
    # Get current attempt number
    attempts_count = db.query(QuizAttempt).filter(
        and_(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.intern_id == intern_id
        )
    ).count()
    
    # Create new attempt
    attempt = QuizAttempt(
        quiz_id=quiz_id,
        intern_id=intern_id,
        attempt_number=attempts_count + 1,
        answers=attempt_data.answers,
        started_at=attempt_data.started_at,
        completed_at=datetime.utcnow()
    )
    
    # Calculate time taken
    if attempt_data.started_at:
        time_diff = datetime.utcnow() - attempt_data.started_at
        attempt.time_taken = int(time_diff.total_seconds())
    
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt

def generate_certificate(
    db: Session,
    intern_id: int,
    module_id: int,
    certificate_type: str = "module"
) -> Certificate:
    """Generate certificate for completed module"""
    # Get module details
    module = get_learning_module(db, module_id)
    if not module:
        raise ValueError("Module not found")
    
    # Get intern details
    intern = db.query(Intern).filter(Intern.id == intern_id).first()
    if not intern:
        raise ValueError("Intern not found")
    
    # Generate unique certificate ID
    certificate_id = str(uuid.uuid4())
    
    # Create certificate record
    certificate = Certificate(
        intern_id=intern_id,
        module_id=module_id,
        certificate_type=certificate_type,
        title=f"Certificate of Completion - {module.title}",
        description=f"This certifies that {intern.user.first_name} {intern.user.last_name} has successfully completed {module.title}",
        certificate_id=certificate_id,
        skills_demonstrated=module.learning_objectives,
        verification_data={
            "intern_name": f"{intern.user.first_name} {intern.user.last_name}",
            "module_title": module.title,
            "completion_date": datetime.utcnow().isoformat(),
            "track": module.track
        }
    )
    
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    
    # TODO: Generate actual PDF certificate and upload to storage
    # certificate.certificate_url = generate_certificate_pdf(certificate)
    
    return certificate

def get_learning_path_for_intern(db: Session, intern_id: int) -> Dict[str, Any]:
    """Get personalized learning path for intern"""
    intern = db.query(Intern).filter(Intern.id == intern_id).first()
    if not intern:
        return {}
    
    # Get modules for intern's track
    track_modules = get_learning_modules(
        db, 
        filters={"track": intern.program_track}
    )
    
    # Get intern's progress
    progress_records = db.query(LearningProgress).filter(
        LearningProgress.intern_id == intern_id
    ).all()
    
    progress_map = {p.module_id: p for p in progress_records}
    
    # Build learning path
    learning_path = {
        "track": intern.program_track,
        "modules": [],
        "total_duration": 0,
        "completed_modules": 0,
        "in_progress_modules": 0
    }
    
    for module in track_modules:
        module_info = {
            "module": module,
            "progress": progress_map.get(module.id),
            "status": "not_started",
            "can_access": True
        }
        
        if module.id in progress_map:
            progress = progress_map[module.id]
            module_info["status"] = progress.status
            if progress.status == "completed":
                learning_path["completed_modules"] += 1
            elif progress.status == "in_progress":
                learning_path["in_progress_modules"] += 1
        
        # Check prerequisites
        if module.prerequisites:
            module_info["can_access"] = check_prerequisites_met(
                db, intern_id, module.id
            )
        
        learning_path["modules"].append(module_info)
        learning_path["total_duration"] += module.estimated_duration or 0
    
    return learning_path

def check_prerequisites_met(db: Session, intern_id: int, module_id: int) -> bool:
    """Check if prerequisites are met for a module"""
    module = get_learning_module(db, module_id)
    if not module or not module.prerequisites:
        return True
    
    # Check if all prerequisite modules are completed
    completed_modules = db.query(LearningProgress.module_id).filter(
        and_(
            LearningProgress.intern_id == intern_id,
            LearningProgress.status == "completed"
        )
    ).all()
    
    completed_module_ids = [m[0] for m in completed_modules]
    
    for prereq_id in module.prerequisites:
        if prereq_id not in completed_module_ids:
            return False
    
    return True
