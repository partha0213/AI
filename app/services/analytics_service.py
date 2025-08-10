# app/services/analytics_service.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus
from app.models.learning import LearningProgress, QuizAttempt, Certificate
from app.models.intern import Intern


# -------- Helper time range --------
def _window(start_date: Optional[datetime], days: int) -> Tuple[datetime, datetime]:
    if start_date is None:
        end = datetime.utcnow()
        start = end - timedelta(days=days)
    else:
        start = start_date
        end = start + timedelta(days=days)
    return start, end


# -------- Public API (used by app/api/v1/analytics.py) --------
def calculate_engagement_metrics(db: Session, start_date: Optional[datetime] = None, days: int = 30) -> Dict[str, Any]:
    """
    Aggregate 'engagement' signals within a window:
    - active_interns: interns who have any progress or quiz attempts
    - avg_time_spent_per_intern: from LearningProgress.time_spent
    - quiz_attempts: total attempts
    """
    start, end = _window(start_date, days)

    # Active interns: any learning progress OR quiz attempt in window
    lp_interns_q = (
        db.query(LearningProgress.intern_id)
        .filter(LearningProgress.last_accessed >= start, LearningProgress.last_accessed < end)
        .distinct()
    )
    qa_interns_q = (
        db.query(QuizAttempt.intern_id)
        .filter(QuizAttempt.created_at >= start, QuizAttempt.created_at < end)
        .distinct()
    )
    active_interns = db.query(func.count(func.distinct(Intern.id))).filter(
        Intern.id.in_(lp_interns_q.union(qa_interns_q))
    ).scalar() or 0

    # Average time spent per intern
    total_time = (
        db.query(func.coalesce(func.sum(LearningProgress.time_spent), 0))
        .filter(LearningProgress.last_accessed >= start, LearningProgress.last_accessed < end)
        .scalar()
        or 0
    )
    avg_time_spent = float(total_time) / active_interns if active_interns else 0.0

    # Quiz attempts
    attempts = (
        db.query(func.count(QuizAttempt.id))
        .filter(QuizAttempt.created_at >= start, QuizAttempt.created_at < end)
        .scalar()
        or 0
    )

    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "active_interns": active_interns,
        "quiz_attempts": attempts,
        "avg_time_spent_per_intern": avg_time_spent,
    }


def get_trend_analysis(db: Session, start_date: Optional[datetime] = None, days: int = 30) -> Dict[str, Any]:
    """
    Daily trend over the window for:
    - tasks_completed
    - quizzes_passed
    - learning_sessions (any LearningProgress activity)
    """
    start, end = _window(start_date, days)

    # Tasks completed per day
    tasks_completed = (
        db.query(func.date(Task.updated_at).label("d"), func.count(Task.id))
        .filter(
            Task.updated_at >= start,
            Task.updated_at < end,
            Task.status == TaskStatus.COMPLETED,
        )
        .group_by(func.date(Task.updated_at))
        .all()
    )

    # Quizzes passed per day
    quizzes_passed = (
        db.query(func.date(QuizAttempt.created_at).label("d"), func.count(QuizAttempt.id))
        .filter(
            QuizAttempt.created_at >= start,
            QuizAttempt.created_at < end,
            QuizAttempt.passed == True,  # noqa: E712
        )
        .group_by(func.date(QuizAttempt.created_at))
        .all()
    )

    # Learning sessions per day (any progress events)
    learning_sessions = (
        db.query(func.date(LearningProgress.last_accessed).label("d"), func.count(LearningProgress.id))
        .filter(LearningProgress.last_accessed >= start, LearningProgress.last_accessed < end)
        .group_by(func.date(LearningProgress.last_accessed))
        .all()
    )

    def rows_to_series(rows):
        return [{"date": str(d), "count": int(c)} for d, c in rows]

    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "tasks_completed": rows_to_series(tasks_completed),
        "quizzes_passed": rows_to_series(quizzes_passed),
        "learning_sessions": rows_to_series(learning_sessions),
    }


def calculate_success_rates(db: Session, start_date: Optional[datetime] = None, days: int = 30) -> Dict[str, Any]:
    """
    Compute pass/completion rates in the window:
    - task_completion_rate
    - quiz_pass_rate
    """
    start, end = _window(start_date, days)

    # Tasks
    total_tasks = (
        db.query(func.count(Task.id))
        .filter(Task.created_at >= start, Task.created_at < end)
        .scalar()
        or 0
    )
    completed_tasks = (
        db.query(func.count(Task.id))
        .filter(
            Task.updated_at >= start,
            Task.updated_at < end,
            Task.status == TaskStatus.COMPLETED,
        )
        .scalar()
        or 0
    )
    task_completion_rate = (completed_tasks / total_tasks) if total_tasks else 0.0

    # Quizzes
    total_attempts = (
        db.query(func.count(QuizAttempt.id))
        .filter(QuizAttempt.created_at >= start, QuizAttempt.created_at < end)
        .scalar()
        or 0
    )
    passed_attempts = (
        db.query(func.count(QuizAttempt.id))
        .filter(
            QuizAttempt.created_at >= start,
            QuizAttempt.created_at < end,
            QuizAttempt.passed == True,  # noqa: E712
        )
        .scalar()
        or 0
    )
    quiz_pass_rate = (passed_attempts / total_attempts) if total_attempts else 0.0

    return {
        "task_completion_rate": task_completion_rate,
        "quiz_pass_rate": quiz_pass_rate,
    }


def get_intern_task_statistics(db: Session, intern_id: int) -> Dict[str, Any]:
    """
    Counts of tasks by status for a given intern.
    """
    status_counts = (
        db.query(Task.status, func.count(Task.id))
        .filter(Task.assigned_intern_id == intern_id)
        .group_by(Task.status)
        .all()
    )
    by_status = {str(s): int(c) for s, c in status_counts}
    total = sum(by_status.values())
    completed = by_status.get(str(TaskStatus.COMPLETED), 0)
    completion_rate = (completed / total) if total else 0.0

    return {"by_status": by_status, "total": total, "completion_rate": completion_rate}


def get_intern_learning_statistics(db: Session, intern_id: int) -> Dict[str, Any]:
    """
    Aggregate learning progress for a given intern.
    """
    # Time spent
    total_time = (
        db.query(func.coalesce(func.sum(LearningProgress.time_spent), 0))
        .filter(LearningProgress.intern_id == intern_id)
        .scalar()
        or 0
    )

    # Modules completed
    modules_completed = (
        db.query(func.count(LearningProgress.id))
        .filter(LearningProgress.intern_id == intern_id, LearningProgress.completed == True)  # noqa: E712
        .scalar()
        or 0
    )

    # Quizzes
    attempts = (
        db.query(func.count(QuizAttempt.id))
        .filter(QuizAttempt.intern_id == intern_id)
        .scalar()
        or 0
    )
    passed = (
        db.query(func.count(QuizAttempt.id))
        .filter(QuizAttempt.intern_id == intern_id, QuizAttempt.passed == True)  # noqa: E712
        .scalar()
        or 0
    )

    return {
        "time_spent": float(total_time),
        "modules_completed": int(modules_completed),
        "quiz_attempts": int(attempts),
        "quizzes_passed": int(passed),
    }


def get_intern_performance_trends(db: Session, intern_id: int, days: int = 30) -> Dict[str, Any]:
    """
    Trend of the intern's quiz scores and module completion over time.
    """
    start = datetime.utcnow() - timedelta(days=days)

    # Quiz score trend
    quiz_scores = (
        db.query(func.date(QuizAttempt.created_at).label("d"), func.avg(QuizAttempt.score))
        .filter(QuizAttempt.intern_id == intern_id, QuizAttempt.created_at >= start)
        .group_by(func.date(QuizAttempt.created_at))
        .all()
    )

    # Modules completed per day
    modules_completed = (
        db.query(func.date(LearningProgress.updated_at).label("d"), func.count(LearningProgress.id))
        .filter(
            LearningProgress.intern_id == intern_id,
            LearningProgress.updated_at >= start,
            LearningProgress.completed == True,  # noqa: E712
        )
        .group_by(func.date(LearningProgress.updated_at))
        .all()
    )

    return {
        "quiz_score_avg_by_day": [{"date": str(d), "avg_score": float(s)} for d, s in quiz_scores],
        "modules_completed_by_day": [{"date": str(d), "count": int(c)} for d, c in modules_completed],
    }


def get_avg_api_response_time() -> float:
    """
    Placeholder: average API response time. In production you’d query Prometheus
    or your APM. Returning 0.0 keeps the endpoint healthy until monitoring is wired.
    """
    return 0.0


def generate_performance_report(
    db: Session,
    start_date: Optional[datetime] = None,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Combined analytics artifact used by the API endpoint.
    """
    engagement = calculate_engagement_metrics(db, start_date, days)
    trends = get_trend_analysis(db, start_date, days)
    success = calculate_success_rates(db, start_date, days)

    # Certificates issued within window
    start, end = _window(start_date, days)
    certs_issued = (
        db.query(func.count(Certificate.id))
        .filter(Certificate.issued_date >= start, Certificate.issued_date < end)
        .scalar()
        or 0
    )

    return {
        "engagement": engagement,
        "trends": trends,
        "success_rates": success,
        "certificates_issued": int(certs_issued),
        "generated_at": datetime.utcnow().isoformat(),
    }
