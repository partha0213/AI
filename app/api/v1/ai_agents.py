from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.ai_agents.coordinator_agent import CoordinatorAgent
from app.ai_agents.assessment_agent import AssessmentAgent
from app.ai_agents.customization_agent import CustomizationAgent
from app.ai_agents.task_manager_agent import TaskManagerAgent
from app.ai_agents.evaluation_agent import EvaluationAgent
from app.services.intern_service import get_intern_by_user_id, get_intern_by_id
from app.services.task_service import get_task_by_id
from app.api.deps import get_current_active_user, get_admin_user, get_mentor_user

router = APIRouter()

# Initialize AI agents
coordinator = CoordinatorAgent()
assessment_agent = AssessmentAgent()
customization_agent = CustomizationAgent()
task_manager_agent = TaskManagerAgent()
evaluation_agent = EvaluationAgent()

@router.post("/onboarding/complete")
async def complete_ai_onboarding(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Trigger complete AI-powered onboarding workflow"""
    
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only interns can trigger onboarding workflow"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    # Prepare intern data for workflow
    intern_data = {
        "id": intern.id,
        "user_id": current_user.id,
        "email": current_user.email,
        "name": f"{current_user.first_name} {current_user.last_name}",
        "program_track": intern.program_track,
        "skills": intern.skills or [],
        "experience_level": intern.experience_level,
        "university": intern.university,
        "major": intern.major
    }
    
    # Execute onboarding workflow
    workflow_result = await coordinator.process({
        "workflow": "new_intern_onboarding",
        "intern_data": intern_data,
        "db": db
    })
    
    if workflow_result.get("success"):
        # Update intern profile with workflow results
        background_tasks.add_task(
            update_intern_with_ai_insights,
            db,
            intern.id,
            workflow_result.get("data", {})
        )
    
    return {
        "message": "AI onboarding workflow completed",
        "workflow_result": workflow_result,
        "next_steps": workflow_result.get("data", {}).get("next_actions", [])
    }

@router.post("/assessment/comprehensive")
async def run_comprehensive_assessment(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Run comprehensive AI assessment for current user"""
    
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only interns can run comprehensive assessments"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    # Run comprehensive evaluation
    evaluation_result = await coordinator.process({
        "workflow": "comprehensive_evaluation",
        "intern_id": intern.id,
        "period": "current",
        "db": db
    })
    
    return {
        "message": "Comprehensive AI assessment completed",
        "evaluation": evaluation_result,
        "recommendations": evaluation_result.get("data", {}).get("action_plan", {})
    }

@router.post("/tasks/allocate/{intern_id}")
async def allocate_tasks_for_intern(
    intern_id: int,
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """AI-powered task allocation for specific intern"""
    
    intern = get_intern_by_id(db, intern_id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern not found"
        )
    
    # Verify mentor has access to this intern
    if (current_user.role.value == "mentor" and 
        current_user.mentor_profile and
        intern.assigned_mentor_id != current_user.mentor_profile.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only allocate tasks for your assigned interns"
        )
    
    # Run task allocation
    allocation_result = await task_manager_agent.process({
        "operation": "allocate_tasks",
        "intern_id": intern_id,
        "db": db
    })
    
    return {
        "message": "AI task allocation completed",
        "allocation_result": allocation_result,
        "recommended_tasks": allocation_result.get("data", {}).get("generated_tasks", [])
    }

@router.post("/tasks/{task_id}/evaluate")
async def evaluate_task_submission(
    task_id: int,
    submission_data: Dict[str, Any],
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """AI-powered evaluation of task submission"""
    
    task = get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )
    
    # Verify mentor owns this task
    if (current_user.role.value == "mentor" and
        current_user.mentor_profile and
        task.created_by_mentor_id != current_user.mentor_profile.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only evaluate your own tasks"
        )
    
    # Get intern profile for context
    intern = get_intern_by_id(db, task.assigned_intern_id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Assigned intern not found"
        )
    
    # Prepare submission data
    enhanced_submission_data = {
        **submission_data,
        "task": {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "requirements": task.deliverables or [],
            "difficulty_level": task.difficulty_level
        },
        "intern_profile": {
            "experience_level": intern.experience_level,
            "skills": intern.skills or [],
            "performance_score": intern.performance_score
        }
    }
    
    # Execute submission processing workflow
    workflow_result = await coordinator.process({
        "workflow": "task_submission_processing",
        "submission_data": enhanced_submission_data,
        "task_id": task_id,
        "intern_id": intern.id,
        "db": db
    })
    
    return {
        "message": "AI evaluation completed",
        "evaluation": workflow_result,
        "feedback": workflow_result.get("data", {}).get("feedback", {}),
        "next_steps": workflow_result.get("data", {}).get("next_steps", [])
    }

@router.post("/learning/customize")
async def customize_learning_path(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate customized learning path using AI"""
    
    if current_user.role.value != "intern":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only interns can customize learning paths"
        )
    
    intern = get_intern_by_user_id(db, current_user.id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern profile not found"
        )
    
    # Prepare intern profile for customization
    intern_profile = {
        "intern_id": intern.id,
        "skills": intern.skills or [],
        "experience_level": intern.experience_level,
        "program_track": intern.program_track,
        "assessment_score": intern.assessment_score or 0,
        "learning_style": intern.learning_style,
        "strengths": intern.skill_assessment.get("strengths", []) if intern.skill_assessment else [],
        "improvement_areas": intern.skill_assessment.get("improvement_areas", []) if intern.skill_assessment else []
    }
    
    # Generate learning path
    learning_path_result = await customization_agent.process({
        "type": "learning_path",
        "intern_profile": intern_profile
    })
    
    return {
        "message": "Customized learning path generated",
        "learning_path": learning_path_result,
        "personalization_level": learning_path_result.get("data", {}).get("customization_level", "moderate")
    }

@router.get("/agents/status")
async def get_ai_agents_status(
    current_user: User = Depends(get_admin_user)
):
    """Get status and health of all AI agents"""
    
    agents_status = {
        "coordinator": {
            "name": coordinator.name,
            "status": "active",
            "last_activity": coordinator.created_at,
            "communication_log_size": len(await coordinator.get_agent_communication_log())
        },
        "assessment": {
            "name": assessment_agent.name,
            "status": "active",
            "last_activity": assessment_agent.created_at
        },
        "customization": {
            "name": customization_agent.name,
            "status": "active", 
            "last_activity": customization_agent.created_at
        },
        "task_manager": {
            "name": task_manager_agent.name,
            "status": "active",
            "last_activity": task_manager_agent.created_at
        },
        "evaluation": {
            "name": evaluation_agent.name,
            "status": "active",
            "last_activity": evaluation_agent.created_at
        }
    }
    
    return {
        "overall_status": "healthy",
        "agents": agents_status,
        "total_agents": len(agents_status),
        "active_agents": len([a for a in agents_status.values() if a["status"] == "active"])
    }

@router.get("/agents/communication-log")
async def get_agents_communication_log(
    limit: int = 50,
    current_user: User = Depends(get_admin_user)
):
    """Get inter-agent communication log"""
    
    communication_log = await coordinator.get_agent_communication_log()
    
    return {
        "communication_log": communication_log[-limit:],
        "total_communications": len(communication_log)
    }

@router.post("/tasks/monitor-progress")
async def monitor_task_progress(
    task_ids: List[int],
    current_user: User = Depends(get_mentor_user),
    db: Session = Depends(get_db)
):
    """Monitor task progress using AI analysis"""
    
    # Verify mentor has access to these tasks
    if current_user.role.value == "mentor" and current_user.mentor_profile:
        # Check each task belongs to this mentor
        for task_id in task_ids:
            task = get_task_by_id(db, task_id)
            if task and task.created_by_mentor_id != current_user.mentor_profile.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You don't have access to task {task_id}"
                )
    
    # Run progress monitoring
    monitoring_result = await task_manager_agent.process({
        "operation": "monitor_progress",
        "task_ids": task_ids,
        "db": db
    })
    
    return {
        "message": "Task progress analysis completed",
        "analysis": monitoring_result,
        "alerts": monitoring_result.get("data", {}).get("at_risk_tasks", []),
        "recommendations": monitoring_result.get("data", {}).get("ai_insights", {}).get("recommendations", [])
    }

# Background task helper function
async def update_intern_with_ai_insights(
    db: Session,
    intern_id: int,
    workflow_data: Dict[str, Any]
):
    """Update intern profile with AI-generated insights"""
    
    # This would update the intern's profile with insights from AI agents
    # Implementation depends on your specific database update patterns
    pass
