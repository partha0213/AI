from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Float, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base

class ModuleDifficulty(enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class ModuleType(enum.Enum):
    VIDEO = "video"
    ARTICLE = "article"
    INTERACTIVE = "interactive"
    QUIZ = "quiz"
    PROJECT = "project"

class LearningModule(Base):
    __tablename__ = "learning_modules"

    id = Column(Integer, primary_key=True, index=True)
    
    # Basic Information
    title = Column(String, nullable=False)
    description = Column(Text)
    content = Column(Text)  # Main learning content
    module_type = Column(String, default=ModuleType.ARTICLE.value)
    
    # Categorization
    track = Column(String)  # e.g., "Web Development", "Data Science"
    category = Column(String)  # e.g., "Frontend", "Backend", "Database"
    tags = Column(JSON)  # List of relevant tags
    
    # Difficulty and Prerequisites
    difficulty = Column(String, default=ModuleDifficulty.BEGINNER.value)
    prerequisites = Column(JSON)  # List of module IDs that must be completed first
    learning_objectives = Column(JSON)  # What students will learn
    
    # Content Details
    estimated_duration = Column(Integer)  # in minutes
    video_url = Column(String)
    materials = Column(JSON)  # Additional resources, links, files
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    order_index = Column(Integer, default=0)  # For ordering modules
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    progress_records = relationship("LearningProgress", back_populates="module")
    quizzes = relationship("Quiz", back_populates="module")

class LearningProgress(Base):
    __tablename__ = "learning_progress"

    id = Column(Integer, primary_key=True, index=True)
    
    # References
    intern_id = Column(Integer, ForeignKey("interns.id"))
    module_id = Column(Integer, ForeignKey("learning_modules.id"))
    
    # Progress Tracking
    status = Column(String, default="not_started")  # not_started, in_progress, completed
    completion_percentage = Column(Float, default=0.0)
    time_spent = Column(Integer, default=0)  # in minutes
    
    # Engagement Metrics
    last_accessed = Column(DateTime)
    access_count = Column(Integer, default=0)
    bookmarked = Column(Boolean, default=False)
    
    # Performance
    quiz_scores = Column(JSON)  # Scores from associated quizzes
    average_score = Column(Float)
    
    # Timestamps
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    intern = relationship("Intern", back_populates="learning_progress")
    module = relationship("LearningModule", back_populates="progress_records")

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    
    # Basic Information
    title = Column(String, nullable=False)
    description = Column(Text)
    instructions = Column(Text)
    
    # Configuration
    module_id = Column(Integer, ForeignKey("learning_modules.id"))
    questions = Column(JSON)  # List of questions with options and correct answers
    time_limit = Column(Integer)  # in minutes, null for unlimited
    passing_score = Column(Float, default=70.0)  # percentage
    max_attempts = Column(Integer, default=3)
    
    # Settings
    randomize_questions = Column(Boolean, default=True)
    show_results_immediately = Column(Boolean, default=True)
    allow_review = Column(Boolean, default=True)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    module = relationship("LearningModule", back_populates="quizzes")
    attempts = relationship("QuizAttempt", back_populates="quiz")

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    
    # References
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    intern_id = Column(Integer, ForeignKey("interns.id"))
    
    # Attempt Details
    attempt_number = Column(Integer)  # 1, 2, 3, etc.
    answers = Column(JSON)  # User's answers
    score = Column(Float)  # Percentage score
    passed = Column(Boolean)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    time_taken = Column(Integer)  # in seconds
    
    # AI Evaluation
    ai_feedback = Column(JSON)  # Detailed AI feedback on answers
    
    # Relationships
    quiz = relationship("Quiz", back_populates="attempts")
    
class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    
    # References
    intern_id = Column(Integer, ForeignKey("interns.id"))
    module_id = Column(Integer, ForeignKey("learning_modules.id"), nullable=True)
    
    # Certificate Details
    certificate_type = Column(String)  # "module", "track", "internship"
    title = Column(String, nullable=False)
    description = Column(Text)
    
    # Verification
    certificate_id = Column(String, unique=True)  # Public verification ID
    issued_date = Column(DateTime, default=datetime.utcnow)
    
    # File Storage
    certificate_url = Column(String)  # URL to generated certificate PDF
    
    # Metadata
    skills_demonstrated = Column(JSON)  # Skills covered
    verification_data = Column(JSON)  # Data for verification
