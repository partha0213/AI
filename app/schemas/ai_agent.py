from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, validator
from enum import Enum

class AgentType(str, Enum):
    ASSESSMENT = "assessment"
    CUSTOMIZATION = "customization" 
    ONBOARDING = "onboarding"
    TASK_MANAGER = "task_manager"
    EVALUATION = "evaluation"
    COORDINATOR = "coordinator"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AIRequestBase(BaseModel):
    agent_type: AgentType
    operation: str
    priority: Optional[str] = "normal"
    context: Optional[Dict[str, Any]] = None

class AssessmentRequest(AIRequestBase):
    agent_type: AgentType = AgentType.ASSESSMENT
    assessment_type: str  # resume_analysis, skill_assessment, quiz_evaluation
    data: Dict[str, Any]
    
    @validator('assessment_type')
    def validate_assessment_type(cls, v):
        valid_types = ['resume_analysis', 'skill_assessment', 'quiz_evaluation']
        if v not in valid_types:
            raise ValueError(f'Assessment type must be one of: {valid_types}')
        return v

class CustomizationRequest(AIRequestBase):
    agent_type: AgentType = AgentType.CUSTOMIZATION
    customization_type: str  # learning_path, project_plan, task_customization
    requirements: Dict[str, Any]
    intern_profile: Optional[Dict[str, Any]] = None
    
    @validator('customization_type')
    def validate_customization_type(cls, v):
        valid_types = ['learning_path', 'project_plan', 'task_customization']
        if v not in valid_types:
            raise ValueError(f'Customization type must be one of: {valid_types}')
        return v

class OnboardingRequest(AIRequestBase):
    agent_type: AgentType = AgentType.ONBOARDING
    onboarding_type: str  # create_profile, welcome_package, setup_environment
    intern_data: Dict[str, Any]
    mentor_data: Optional[Dict[str, Any]] = None

class TaskManagerRequest(AIRequestBase):
    agent_type: AgentType = AgentType.TASK_MANAGER
    operation: str  # allocate_tasks, generate_task, monitor_progress
    task_data: Optional[Dict[str, Any]] = None
    intern_id: Optional[int] = None
    
class EvaluationRequest(AIRequestBase):
    agent_type: AgentType = AgentType.EVALUATION
    evaluation_type: str  # code_submission, project_submission, written_assignment
    submission_data: Dict[str, Any]
    evaluation_criteria: Optional[Dict[str, Any]] = None

class CoordinatorRequest(AIRequestBase):
    agent_type: AgentType = AgentType.COORDINATOR
    workflow: str  # new_intern_onboarding, task_submission_processing
    workflow_data: Dict[str, Any]

class AIResponse(BaseModel):
    """Standard AI agent response"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: str
    agent: str
    timestamp: datetime
    processing_time: Optional[float] = None
    confidence_score: Optional[float] = None
    
    class Config:
        from_attributes = True

class AssessmentResult(BaseModel):
    """Assessment agent response"""
    overall_score: float
    skill_breakdown: Dict[str, float]
    strengths: List[str]
    improvement_areas: List[str]
    recommended_track: Optional[str] = None
    personality_traits: Optional[Dict[str, Any]] = None
    learning_style: Optional[str] = None
    
    @validator('overall_score')
    def validate_score(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Score must be between 0 and 100')
        return v

class CustomizationResult(BaseModel):
    """Customization agent response"""
    customization_type: str
    generated_content: Dict[str, Any]
    personalization_level: str
    estimated_effectiveness: float
    implementation_notes: List[str]

class OnboardingResult(BaseModel):
    """Onboarding agent response"""
    profile_created: bool
    welcome_package: Dict[str, Any]
    next_steps: List[str]
    estimated_completion_time: str
    success_indicators: List[str]

class TaskManagerResult(BaseModel):
    """Task manager agent response"""
    operation_type: str
    tasks_generated: Optional[List[Dict[str, Any]]] = None
    allocation_strategy: Optional[Dict[str, Any]] = None
    progress_analysis: Optional[Dict[str, Any]] = None
    recommendations: List[str]

class EvaluationResult(BaseModel):
    """Evaluation agent response"""
    overall_score: float
    category_scores: Dict[str, float]
    detailed_feedback: str
    strengths: List[str]
    improvements_needed: List[str]
    grade_justification: str
    estimated_time_spent: Optional[int] = None
    meets_requirements: bool
    
    @validator('overall_score')
    def validate_score(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Score must be between 0 and 100')
        return v

class WorkflowResult(BaseModel):
    """Coordinator workflow response"""
    workflow_type: str
    steps_completed: List[str]
    results: Dict[str, Any]
    recommendations: Dict[str, Any]
    next_actions: List[str]
    success_rate: float

class AISessionCreate(BaseModel):
    """Create AI session"""
    session_type: str
    agent_name: str
    input_data: Dict[str, Any]
    user_id: int
    intern_id: Optional[int] = None
    task_id: Optional[int] = None

class AISessionResponse(BaseModel):
    """AI session response"""
    id: int
    session_type: str
    agent_name: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    status: ProcessingStatus
    processing_time: Optional[float] = None
    error_message: Optional[str] = None
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    confidence_score: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class AgentMetrics(BaseModel):
    """AI agent performance metrics"""
    agent_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_processing_time: float
    average_confidence_score: float
    total_tokens_used: int
    total_cost: float
    success_rate: float
    last_24h_requests: int
    
class AgentStatus(BaseModel):
    """AI agent status"""
    agent_name: str
    status: str  # active, inactive, error
    last_activity: datetime
    current_load: int
    max_capacity: int
    health_score: float
    error_rate: float
