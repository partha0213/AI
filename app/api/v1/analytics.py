from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.intern import Intern
from app.models.mentor import Mentor
from app.models.task import Task
from app.models.learning import LearningProgress, QuizAttempt
from app.schemas.analytics import (
    DashboardMetrics,
    InternAnalytics,
    MentorAnalytics,
    TaskAnalytics,
    LearningAnalytics,
    SystemMetrics
)
from app.services.analytics_service import (
    calculate_engagement_metrics,
    generate_performance_report,
    get_trend_analysis,
    calculate_success_rates
)
from app.api.deps import get_current_active_user, get_admin_user, get_mentor_user

router = APIRouter()

@router.get("/dashboard", response_model=DashboardMetrics)
async def get_admin_dashboard(
    date_range: Optional[str] = Query("30d", regex="^(7d|30d|90d|1y)$"),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive admin dashboard metrics"""
    
    # Calculate date range
    days_map = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
    days = days_map[date_range]
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Overall Statistics
    total_interns = db.query(Intern).count()
    active_interns = db.query(Intern).filter(Intern.status == "active").count()
    total_mentors = db.query(Mentor).count()
    available_mentors = db.query(Mentor).filter(Mentor.is_available == True).count()
    
    # Task Statistics
    total_tasks = db.query(Task).filter(Task.created_at >= start_date).count()
    completed_tasks = db.query(Task).filter(
        and_(
            Task.status == "completed",
            Task.created_at >= start_date
        )
    ).count()
    
    # Learning Statistics
    modules_completed = db.query(LearningProgress).filter(
        and_(
            LearningProgress.status == "completed",
            LearningProgress.completed_at >= start_date
        )
    ).count()
    
    # Performance Metrics
    avg_task_completion_time = db.query(
        func.avg(
            func.extract('epoch', Task.completed_date - Task.assigned_date) / 3600
        )
    ).filter(
        and_(
            Task.status == "completed",
            Task.completed_date >= start_date
        )
    ).scalar() or 0
    
    # Engagement Metrics
    engagement_data = calculate_engagement_metrics(db, start_date)
    
    # Trend Analysis
    trends = get_trend_analysis(db, start_date, days)
    
    dashboard_metrics = {
        "overview": {
            "total_interns": total_interns,
            "active_interns": active_interns,
            "total_mentors": total_mentors,
            "available_mentors": available_mentors,
            "intern_to_mentor_ratio": round(active_interns / available_mentors, 2) if available_mentors > 0 else 0
        },
        "tasks": {
            "total_assigned": total_tasks,
            "completed": completed_tasks,
            "completion_rate": round((completed_tasks / total_tasks) * 100, 2) if total_tasks > 0 else 0,
            "avg_completion_time": round(avg_task_completion_time, 2)
        },
        "learning": {
            "modules_completed": modules_completed,
            "avg_progress": engagement_data.get("avg_learning_progress", 0),
            "total_certificates_issued": get_certificates_issued_count(db, start_date)
        },
        "engagement": engagement_data,
        "trends": trends,
        "performance": {
            "overall_satisfaction": calculate_overall_satisfaction(db, start_date),
            "retention_rate": calculate_retention_rate(db, start_date),
            "success_rate": calculate_success_rates(db, start_date)
        }
    }
    
    return dashboard_metrics

@router.get("/interns/{intern_id}", response_model=InternAnalytics)
async def get_intern_analytics(
    intern_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed analytics for specific intern"""
    
    # Permission check
    can_access = False
    if current_user.role in [UserRole.ADMIN, UserRole.HR]:
        can_access = True
    elif current_user.role == UserRole.MENTOR:
        mentor = get_mentor_by_user_id(db, current_user.id)
        intern = get_intern_by_id(db, intern_id)
        can_access = (mentor and intern and intern.assigned_mentor_id == mentor.id)
    elif current_user.role == UserRole.INTERN:
        intern = get_intern_by_user_id(db, current_user.id)
        can_access = (intern and intern.id == intern_id)
    
    if not can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    intern = get_intern_by_id(db, intern_id)
    if not intern:
        raise HTTPException(
            status_code=404,
            detail="Intern not found"
        )
    
    # Task Analytics
    task_stats = get_intern_task_statistics(db, intern_id)
    
    # Learning Analytics
    learning_stats = get_intern_learning_statistics(db, intern_id)
    
    # Performance Trends
    performance_trends = get_intern_performance_trends(db, intern_id)
    
    # Skill Development
    skill_development = analyze_skill_development(db, intern_id)
    
    # Time Analytics
    time_analytics = calculate_time_analytics(db, intern_id)
    
    intern_analytics = {
        "intern_info": {
            "id": intern.id,
            "name": f"{intern.user.first_name} {intern.user.last_name}",
            "program_track": intern.program_track,
            "start_date": intern.start_date,
            "status": intern.status,
            "overall_performance": intern.performance_score
        },
        "task_performance": task_stats,
        "learning_progress": learning_stats,
        "skill_development": skill_development,
        "performance_trends": performance_trends,
        "time_analytics": time_analytics,
        "engagement_metrics": {
            "login_frequency": calculate_login_frequency(db, intern.user_id),
            "avg_session_duration": calculate_avg_session_duration(db, intern.user_id),
            "last_activity": get_last_activity_date(db, intern.user_id)
        }
    }
    
    return intern_analytics

@router.get("/mentors/{mentor_id}", response_model=MentorAnalytics)
async def get_mentor_analytics(
    mentor_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get detailed analytics for specific mentor (admin only)"""
    
    mentor = get_mentor_by_id(db, mentor_id)
    if not mentor:
        raise HTTPException(
            status_code=404,
            detail="Mentor not found"
        )
    
    # Mentorship Statistics
    mentorship_stats = get_mentor_statistics(db, mentor_id)
    
    # Intern Outcomes
    intern_outcomes = analyze_mentor_intern_outcomes(db, mentor_id)
    
    # Feedback Analytics
    feedback_analytics = analyze_mentor_feedback(db, mentor_id)
    
    # Performance Metrics
    performance_metrics = calculate_mentor_performance_metrics(db, mentor_id)
    
    mentor_analytics = {
        "mentor_info": {
            "id": mentor.id,
            "name": f"{mentor.user.first_name} {mentor.user.last_name}",
            "designation": mentor.designation,
            "department": mentor.department,
            "experience_years": mentor.years_of_experience,
            "expertise_areas": mentor.expertise_areas
        },
        "mentorship_stats": mentorship_stats,
        "intern_outcomes": intern_outcomes,
        "feedback_analytics": feedback_analytics,
        "performance_metrics": performance_metrics,
        "capacity_utilization": {
            "current_interns": mentor.current_interns_count,
            "max_capacity": mentor.max_interns,
            "utilization_rate": (mentor.current_interns_count / mentor.max_interns) * 100 if mentor.max_interns > 0 else 0
        }
    }
    
    return mentor_analytics

@router.get("/tasks/overview", response_model=TaskAnalytics)
async def get_task_analytics_overview(
    date_range: Optional[str] = Query("30d"),
    track: Optional[str] = None,
    mentor_id: Optional[int] = None,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive task analytics"""
    
    days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}[date_range]
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Base query
    query = db.query(Task).filter(Task.created_at >= start_date)
    
    # Apply filters
    if track:
        query = query.join(Intern).filter(Intern.program_track == track)
    if mentor_id:
        query = query.filter(Task.created_by_mentor_id == mentor_id)
    
    tasks = query.all()
    
    # Task Distribution
    task_distribution = analyze_task_distribution(tasks)
    
    # Completion Analysis
    completion_analysis = analyze_task_completion(tasks)
    
    # Difficulty Analysis
    difficulty_analysis = analyze_task_difficulty_performance(tasks)
    
    # Time Analysis
    time_analysis = analyze_task_time_metrics(tasks)
    
    task_analytics = {
        "summary": {
            "total_tasks": len(tasks),
            "completed_tasks": len([t for t in tasks if t.status == "completed"]),
            "avg_completion_rate": completion_analysis.get("avg_completion_rate", 0),
            "avg_score": completion_analysis.get("avg_score", 0)
        },
        "distribution": task_distribution,
        "completion_analysis": completion_analysis,
        "difficulty_analysis": difficulty_analysis,
        "time_analysis": time_analysis,
        "category_performance": analyze_category_performance(tasks)
    }
    
    return task_analytics

@router.get("/learning/overview", response_model=LearningAnalytics)
async def get_learning_analytics_overview(
    date_range: Optional[str] = Query("30d"),
    track: Optional[str] = None,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive learning analytics"""
    
    days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}[date_range]
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Learning Progress Analysis
    progress_analysis = analyze_learning_progress(db, start_date, track)
    
    # Module Performance
    module_performance = analyze_module_performance(db, start_date, track)
    
    # Quiz Analytics
    quiz_analytics = analyze_quiz_performance(db, start_date)
    
    # Engagement Analysis
    engagement_analysis = analyze_learning_engagement(db, start_date)
    
    learning_analytics = {
        "summary": {
            "total_learners": progress_analysis.get("total_learners", 0),
            "modules_completed": progress_analysis.get("modules_completed", 0),
            "avg_completion_rate": progress_analysis.get("avg_completion_rate", 0),
            "certificates_issued": get_certificates_issued_count(db, start_date)
        },
        "progress_analysis": progress_analysis,
        "module_performance": module_performance,
        "quiz_analytics": quiz_analytics,
        "engagement_analysis": engagement_analysis,
        "track_comparison": compare_track_performance(db, start_date) if not track else None
    }
    
    return learning_analytics

@router.get("/reports/performance")
async def generate_performance_report(
    report_type: str = Query(..., regex="^(intern|mentor|overall|track)$"),
    format: str = Query("json", regex="^(json|csv|pdf)$"),
    date_range: str = Query("30d"),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Generate detailed performance reports"""
    
    days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}[date_range]
    start_date = datetime.utcnow() - timedelta(days=days)
    
    report_data = generate_performance_report(
        db=db,
        report_type=report_type,
        start_date=start_date,
        format=format
    )
    
    if format == "json":
        return report_data
    elif format == "csv":
        # Return CSV file
        return generate_csv_response(report_data)
    else:  # PDF
        # Return PDF file
        return generate_pdf_response(report_data)

@router.get("/system/metrics", response_model=SystemMetrics)
async def get_system_metrics(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get system performance and health metrics"""
    
    # Database metrics
    db_metrics = {
        "total_users": db.query(User).count(),
        "total_interns": db.query(Intern).count(),
        "total_mentors": db.query(Mentor).count(),
        "total_tasks": db.query(Task).count(),
        "total_learning_modules": db.query(LearningModule).count()
    }
    
    # Performance metrics
    performance_metrics = {
        "avg_response_time": get_avg_api_response_time(),
        "active_sessions": get_active_sessions_count(),
        "daily_active_users": get_daily_active_users(db),
        "peak_usage_times": analyze_usage_patterns(db)
    }
    
    # Resource utilization
    resource_metrics = {
        "storage_usage": get_storage_usage(),
        "ai_api_usage": get_ai_api_usage_stats(),
        "email_delivery_rate": get_email_delivery_stats()
    }
    
    system_metrics = {
        "database": db_metrics,
        "performance": performance_metrics,
        "resources": resource_metrics,
        "health_status": "healthy",  # Could be determined by various checks
        "last_updated": datetime.utcnow()
    }
    
    return system_metrics

@router.get("/export/data")
async def export_analytics_data(
    data_type: str = Query(..., regex="^(interns|mentors|tasks|learning|all)$"),
    format: str = Query("csv", regex="^(csv|json|excel)$"),
    date_range: str = Query("30d"),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Export analytics data in various formats"""
    
    days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}[date_range]
    start_date = datetime.utcnow() - timedelta(days=days)
    
    export_data = prepare_export_data(db, data_type, start_date)
    
    if format == "json":
        return export_data
    elif format == "csv":
        return generate_csv_export(export_data, data_type)
    else:  # Excel
        return generate_excel_export(export_data, data_type)
