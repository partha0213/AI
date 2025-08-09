from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class DashboardMetrics(BaseModel):
    """Admin dashboard metrics"""
    overview: Dict[str, Any]
    tasks: Dict[str, Any]
    learning: Dict[str, Any]
    engagement: Dict[str, Any]
    trends: Dict[str, Any]
    performance: Dict[str, Any]

class InternAnalytics(BaseModel):
    """Individual intern analytics"""
    intern_info: Dict[str, Any]
    task_performance: Dict[str, Any]
    learning_progress: Dict[str, Any]
    skill_development: Dict[str, Any]
    performance_trends: Dict[str, Any]
    time_analytics: Dict[str, Any]
    engagement_metrics: Dict[str, Any]

class MentorAnalytics(BaseModel):
    """Individual mentor analytics"""
    mentor_info: Dict[str, Any]
    mentorship_stats: Dict[str, Any]
    intern_outcomes: Dict[str, Any]
    feedback_analytics: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    capacity_utilization: Dict[str, Any]

class TaskAnalytics(BaseModel):
    """Task analytics overview"""
    summary: Dict[str, Any]
    distribution: Dict[str, Any]
    completion_analysis: Dict[str, Any]
    difficulty_analysis: Dict[str, Any]
    time_analysis: Dict[str, Any]
    category_performance: Dict[str, Any]

class LearningAnalytics(BaseModel):
    """Learning analytics overview"""
    summary: Dict[str, Any]
    progress_analysis: Dict[str, Any]
    module_performance: Dict[str, Any]
    quiz_analytics: Dict[str, Any]
    engagement_analysis: Dict[str, Any]
    track_comparison: Optional[Dict[str, Any]] = None

class SystemMetrics(BaseModel):
    """System performance metrics"""
    database: Dict[str, Any]
    performance: Dict[str, Any]
    resources: Dict[str, Any]
    health_status: str
    last_updated: datetime

class PerformanceReport(BaseModel):
    """Performance report data"""
    report_type: str
    date_range: str
    summary: Dict[str, Any]
    detailed_metrics: Dict[str, Any]
    recommendations: List[str]
    charts_data: Dict[str, Any]
    generated_at: datetime

class UsageStatistics(BaseModel):
    """Usage statistics"""
    period: str
    total_users: int
    active_users: int
    total_sessions: int
    average_session_duration: float
    popular_features: List[Dict[str, Any]]
    user_satisfaction: float
    growth_metrics: Dict[str, Any]
