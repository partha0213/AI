import openai
import json
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import re
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential
import hashlib

from app.core.config import settings
from app.core.exceptions import AIProcessingError, InsufficientCreditsError
from app.ai_agents.coordinator_agent import CoordinatorAgent
from app.ai_agents.assessment_agent import AssessmentAgent
from app.ai_agents.customization_agent import CustomizationAgent
from app.ai_agents.onboarding_agent import OnboardingAgent
from app.ai_agents.task_manager_agent import TaskManagerAgent
from app.ai_agents.evaluation_agent import EvaluationAgent

# Configure OpenAI
openai.api_key = settings.OPENAI_API_KEY

# Setup logger
logger = logging.getLogger("ai_service")

class AIService:
    """Central AI service for coordinating all AI operations with enhanced error handling"""
    
    def __init__(self):
        # Initialize AI agents
        self.coordinator = CoordinatorAgent()
        self.assessment_agent = AssessmentAgent()
        self.customization_agent = CustomizationAgent()
        self.onboarding_agent = OnboardingAgent()
        self.task_manager_agent = TaskManagerAgent()
        self.evaluation_agent = EvaluationAgent()
        
        # AI service metrics
        self.request_count = 0
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.error_count = 0
        self.success_count = 0
        self.start_time = datetime.utcnow()
        
        # Circuit breaker state
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure = None
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 300  # 5 minutes
        
        # Model configurations
        self.models = {
            "text_generation": "gpt-4",
            "code_analysis": "gpt-4",
            "resume_analysis": "gpt-3.5-turbo",
            "skill_assessment": "gpt-4",
            "content_creation": "gpt-4"
        }
        
        # Token costs (per 1K tokens)
        self.token_costs = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002}
        }
        
        # Request timeout settings
        self.max_retries = 3
        self.timeout = 30
        self.backoff_factor = 2

    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open"""
        if self.circuit_breaker_failures < self.circuit_breaker_threshold:
            return False
        
        if self.circuit_breaker_last_failure:
            time_since_failure = (datetime.utcnow() - self.circuit_breaker_last_failure).total_seconds()
            if time_since_failure > self.circuit_breaker_timeout:
                # Reset circuit breaker
                self.circuit_breaker_failures = 0
                self.circuit_breaker_last_failure = None
                return False
        
        return True

    def _record_failure(self):
        """Record a failure for circuit breaker"""
        self.circuit_breaker_failures += 1
        self.circuit_breaker_last_failure = datetime.utcnow()
        self.error_count += 1

    def _record_success(self):
        """Record a success"""
        self.circuit_breaker_failures = max(0, self.circuit_breaker_failures - 1)
        self.success_count += 1

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def safe_openai_call(self, **kwargs):
        """Make OpenAI API call with comprehensive error handling and retry logic"""
        
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            logger.error("Circuit breaker is open, rejecting AI request")
            raise AIProcessingError("AI service temporarily unavailable due to repeated failures")
        
        try:
            # Set timeout
            kwargs['request_timeout'] = self.timeout
            
            # Add request tracking
            start_time = time.time()
            logger.info(f"Making OpenAI API call with model: {kwargs.get('model', 'unknown')}")
            
            response = await openai.ChatCompletion.acreate(**kwargs)
            
            # Track usage and success
            processing_time = time.time() - start_time
            self._track_usage(response, processing_time)
            self._record_success()
            
            logger.info(f"OpenAI API call successful in {processing_time:.2f}s")
            return response
            
        except openai.error.RateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded: {str(e)}")
            self._record_failure()
            raise AIProcessingError("AI service rate limit exceeded. Please try again later.")
            
        except openai.error.AuthenticationError as e:
            logger.error(f"OpenAI authentication failed: {str(e)}")
            self._record_failure()
            raise AIProcessingError("AI service authentication failed.")
            
        except openai.error.InvalidRequestError as e:
            logger.error(f"Invalid OpenAI request: {str(e)}")
            self._record_failure()
            raise AIProcessingError(f"Invalid AI request: {str(e)}")
            
        except openai.error.InsufficientQuotaError as e:
            logger.error(f"OpenAI quota exceeded: {str(e)}")
            self._record_failure()
            raise InsufficientCreditsError("AI service quota exceeded.")
            
        except openai.error.ServiceUnavailableError as e:
            logger.error(f"OpenAI service unavailable: {str(e)}")
            self._record_failure()
            raise AIProcessingError("AI service temporarily unavailable.")
            
        except asyncio.TimeoutError:
            logger.error("OpenAI request timeout")
            self._record_failure()
            raise AIProcessingError("AI service request timeout.")
            
        except Exception as e:
            logger.error(f"Unexpected AI service error: {str(e)}")
            self._record_failure()
            raise AIProcessingError(f"AI service error: {str(e)}")

    async def analyze_resume_ai(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Analyze resume using AI with enhanced error handling"""
        try:
            # Check for prompt injection in filename
            if self._contains_prompt_injection(filename):
                logger.warning(f"Potential prompt injection detected in filename: {filename}")
                filename = "resume_file"
            
            # Extract text from resume (with fallback)
            text_content = self._extract_text_from_resume(content, filename)
            
            # Sanitize content to prevent prompt injection
            text_content = self._sanitize_ai_input(text_content)
            
            # Truncate if too long (prevent token limit issues)
            text_content = self._truncate_content(text_content, max_tokens=3000)
            
            analysis_prompt = f"""
            Analyze this resume and extract key information:
            
            Resume Content:
            {text_content}
            
            Provide comprehensive analysis in JSON format:
            1. personal_info: Name, contact details, location
            2. education: Schools, degrees, graduation dates, GPA if available
            3. experience: Work experience with roles, companies, durations
            4. skills: Technical and soft skills identified
            5. projects: Any projects mentioned with descriptions
            6. achievements: Awards, certifications, notable accomplishments
            7. summary: Professional summary or objective
            8. strengths: Key strengths identified from content
            9. improvement_areas: Areas that could be improved in resume
            10. recommended_tracks: Suitable internship tracks based on background
            11. experience_level: Estimated experience level (beginner/intermediate/advanced)
            12. overall_score: Resume quality score out of 100
            
            Return only valid JSON.
            """
            
            response = await self.safe_openai_call(
                model=self.models["resume_analysis"],
                messages=[
                    {"role": "system", "content": "You are an expert resume analyst and career counselor."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.2,
                max_tokens=2000
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            # Add metadata
            analysis["analysis_metadata"] = {
                "processed_at": datetime.utcnow().isoformat(),
                "model_used": self.models["resume_analysis"],
                "content_length": len(text_content),
                "filename": filename
            }
            
            logger.info(f"Resume analysis completed for file: {filename}")
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {str(e)}")
            # Return fallback analysis
            return await self._fallback_resume_analysis(content, filename)
            
        except Exception as e:
            logger.error(f"Resume analysis failed: {str(e)}")
            # Return fallback analysis instead of raising exception
            return await self._fallback_resume_analysis(content, filename)

    async def assess_skills_ai(self, intern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess intern skills using AI with enhanced validation"""
        try:
            # Validate input data
            if not intern_data or not isinstance(intern_data, dict):
                raise AIProcessingError("Invalid intern data provided")
            
            # Sanitize input data
            sanitized_data = self._sanitize_dict_values(intern_data)
            
            assessment_prompt = f"""
            Assess the skills and capabilities of this intern based on their profile:
            
            Intern Profile:
            - Skills Listed: {sanitized_data.get('skills', [])}
            - Experience Level: {sanitized_data.get('experience_level', 'beginner')}
            - Education: {sanitized_data.get('education', {})}
            - Previous Experience: {sanitized_data.get('experience', 'None provided')}
            - Projects: {sanitized_data.get('projects', [])}
            
            Provide detailed skills assessment in JSON format:
            1. technical_skills: Assessment of each technical skill with proficiency level
            2. soft_skills: Identified soft skills with ratings
            3. skill_gaps: Skills missing for their desired track
            4. learning_recommendations: Specific skills to focus on improving
            5. strengths: Top 5 strengths identified
            6. development_areas: Top 5 areas for development
            7. readiness_score: Overall readiness for internship (0-100)
            8. recommended_learning_path: Suggested learning sequence
            9. personality_traits: Inferred personality traits for mentorship
            10. learning_style: Recommended learning approach
            
            Be specific and actionable in your recommendations.
            Return only valid JSON.
            """
            
            response = await self.safe_openai_call(
                model=self.models["skill_assessment"],
                messages=[
                    {"role": "system", "content": "You are an expert skills assessor and learning path designer for technology internships."},
                    {"role": "user", "content": assessment_prompt}
                ],
                temperature=0.3,
                max_tokens=2500
            )
            
            assessment = json.loads(response.choices[0].message.content)
            
            # Add assessment metadata
            assessment["assessment_metadata"] = {
                "assessed_at": datetime.utcnow().isoformat(),
                "model_used": self.models["skill_assessment"],
                "data_quality_score": self._calculate_data_quality_score(intern_data)
            }
            
            logger.info("Skills assessment completed successfully")
            return assessment
            
        except Exception as e:
            logger.error(f"Skills assessment failed: {str(e)}")
            # Return fallback assessment
            return self._fallback_skills_assessment(intern_data)

    async def auto_grade_submission(
        self, 
        task_data: Dict[str, Any], 
        submission_data: Dict[str, Any],
        intern_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Auto-grade task submission using AI with comprehensive validation"""
        try:
            # Validate inputs
            if not all([task_data, submission_data, intern_profile]):
                raise AIProcessingError("Missing required data for auto-grading")
            
            # Sanitize inputs
            task_data = self._sanitize_dict_values(task_data)
            submission_data = self._sanitize_dict_values(submission_data)
            intern_profile = self._sanitize_dict_values(intern_profile)
            
            evaluation_request = {
                "type": "code_submission",  # Could be determined from task
                "submission_data": {
                    **submission_data,
                    "task": task_data,
                    "intern_profile": intern_profile
                }
            }
            
            # Use evaluation agent with timeout
            try:
                evaluation_result = await asyncio.wait_for(
                    self.evaluation_agent.process(evaluation_request),
                    timeout=60  # 1 minute timeout for evaluation
                )
            except asyncio.TimeoutError:
                logger.error("Evaluation agent timeout")
                return self._fallback_evaluation(task_data, submission_data)
            
            if not evaluation_result.get("success"):
                logger.warning("Evaluation agent failed, using fallback")
                return self._fallback_evaluation(task_data, submission_data)
            
            logger.info(f"Auto-grading completed for task {task_data.get('id')}")
            return evaluation_result.get("data", {})
            
        except Exception as e:
            logger.error(f"Auto-grading failed: {str(e)}")
            # Return fallback evaluation
            return self._fallback_evaluation(task_data, submission_data)

    async def generate_personalized_content(
        self, 
        content_type: str, 
        user_profile: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate personalized content using AI with validation"""
        try:
            # Validate content type
            allowed_content_types = [
                "learning_path", "project_plan", "task_customization", 
                "welcome_message", "progress_report"
            ]
            
            if content_type not in allowed_content_types:
                raise AIProcessingError(f"Invalid content type: {content_type}")
            
            # Sanitize inputs
            user_profile = self._sanitize_dict_values(user_profile)
            context = self._sanitize_dict_values(context) if context else {}
            
            customization_request = {
                "type": content_type,
                "requirements": context,
                "intern_profile": user_profile
            }
            
            # Use customization agent with timeout
            try:
                content_result = await asyncio.wait_for(
                    self.customization_agent.process(customization_request),
                    timeout=45
                )
            except asyncio.TimeoutError:
                logger.error("Customization agent timeout")
                return self._fallback_content_generation(content_type, user_profile)
            
            if not content_result.get("success"):
                logger.warning("Content generation failed, using fallback")
                return self._fallback_content_generation(content_type, user_profile)
            
            logger.info(f"Personalized content generated: {content_type}")
            return content_result.get("data", {})
            
        except Exception as e:
            logger.error(f"Content generation failed: {str(e)}")
            return self._fallback_content_generation(content_type, user_profile)

    async def get_ai_service_health(self) -> Dict[str, Any]:
        """Get comprehensive AI service health status"""
        try:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            
            # Test OpenAI connectivity
            try:
                test_response = await asyncio.wait_for(
                    self.safe_openai_call(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": "Test"}],
                        max_tokens=5
                    ),
                    timeout=10
                )
                openai_status = "healthy"
            except:
                openai_status = "unhealthy"
            
            total_requests = self.success_count + self.error_count
            success_rate = (self.success_count / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "status": "healthy" if openai_status == "healthy" and not self._is_circuit_breaker_open() else "unhealthy",
                "uptime_seconds": int(uptime),
                "circuit_breaker_open": self._is_circuit_breaker_open(),
                "openai_connectivity": openai_status,
                "metrics": {
                    "total_requests": total_requests,
                    "successful_requests": self.success_count,
                    "failed_requests": self.error_count,
                    "success_rate": round(success_rate, 2),
                    "total_tokens_used": self.total_tokens_used,
                    "total_cost": round(self.total_cost, 4)
                },
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_updated": datetime.utcnow().isoformat()
            }

    # Helper methods for security and fallbacks
    def _contains_prompt_injection(self, text: str) -> bool:
        """Check for potential prompt injection attempts"""
        dangerous_patterns = [
            "ignore previous instructions",
            "system:",
            "assistant:",
            "###",
            "act as",
            "pretend to be",
            "jailbreak",
            "dev mode"
        ]
        
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in dangerous_patterns)

    def _sanitize_ai_input(self, text: str) -> str:
        """Sanitize input to prevent prompt injection"""
        if self._contains_prompt_injection(text):
            logger.warning("Potential prompt injection detected, sanitizing input")
            # Remove dangerous patterns
            dangerous_patterns = [
                r"ignore previous instructions",
                r"system:",
                r"assistant:",
                r"###",
                r"act as.*",
                r"pretend to be.*"
            ]
            
            for pattern in dangerous_patterns:
                text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
        
        # Limit length to prevent token overflow
        return text[:10000]  # Reasonable limit for most use cases

    def _sanitize_dict_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionary values"""
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = self._sanitize_ai_input(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict_values(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_ai_input(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized

    def _truncate_content(self, content: str, max_tokens: int = 3000) -> str:
        """Truncate content to prevent token limit issues"""
        # Rough estimation: 1 token ≈ 4 characters
        max_chars = max_tokens * 4
        if len(content) > max_chars:
            logger.info(f"Truncating content from {len(content)} to {max_chars} characters")
            return content[:max_chars] + "...[truncated]"
        return content

    def _calculate_data_quality_score(self, data: Dict[str, Any]) -> float:
        """Calculate data quality score for assessment reliability"""
        score = 0.0
        max_score = 100.0
        
        # Check for presence of key fields
        if data.get('skills'):
            score += 20
        if data.get('experience'):
            score += 20
        if data.get('education'):
            score += 20
        if data.get('projects'):
            score += 20
        if data.get('experience_level'):
            score += 20
        
        return min(score, max_score)

    # Fallback methods
    async def _fallback_resume_analysis(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Fallback resume analysis when AI fails"""
        logger.info("Using fallback resume analysis")
        return {
            "status": "fallback",
            "message": "AI analysis temporarily unavailable",
            "filename": filename,
            "size_bytes": len(content),
            "overall_score": 50,
            "personal_info": {"name": "Unable to extract", "email": "Unable to extract"},
            "education": [],
            "experience": [],
            "skills": [],
            "projects": [],
            "achievements": [],
            "summary": "Resume uploaded successfully. AI analysis will be available shortly.",
            "strengths": ["Resume submitted for review"],
            "improvement_areas": ["AI analysis pending"],
            "recommended_tracks": ["General"],
            "experience_level": "beginner",
            "analysis_metadata": {
                "processed_at": datetime.utcnow().isoformat(),
                "fallback_used": True,
                "reason": "AI service unavailable"
            }
        }

    def _fallback_skills_assessment(self, intern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback skills assessment"""
        logger.info("Using fallback skills assessment")
        return {
            "status": "fallback", 
            "technical_skills": {},
            "soft_skills": {},
            "skill_gaps": [],
            "learning_recommendations": ["Complete basic programming tutorials"],
            "strengths": ["Motivated to learn"],
            "development_areas": ["Technical skills development needed"],
            "readiness_score": 50,
            "recommended_learning_path": ["Start with fundamentals"],
            "personality_traits": {"learning_oriented": True},
            "learning_style": "visual",
            "assessment_metadata": {
                "assessed_at": datetime.utcnow().isoformat(),
                "fallback_used": True,
                "reason": "AI service unavailable"
            }
        }

    def _fallback_evaluation(self, task_data: Dict[str, Any], submission_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback evaluation when AI fails"""
        logger.info("Using fallback evaluation")
        return {
            "status": "fallback",
            "overall_score": 75,  # Neutral score
            "category_scores": {
                "functionality": 75,
                "code_quality": 75,
                "documentation": 75
            },
            "detailed_feedback": "Submission received successfully. AI evaluation will be processed shortly.",
            "strengths": ["Submission completed on time"],
            "improvements_needed": ["Detailed AI feedback pending"],
            "grade_justification": "Basic submission requirements met. Detailed evaluation pending.",
            "meets_requirements": True,
            "fallback_used": True,
            "evaluation_pending": True
        }

    def _fallback_content_generation(self, content_type: str, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback content generation"""
        logger.info(f"Using fallback content generation for: {content_type}")
        return {
            "status": "fallback",
            "content_type": content_type,
            "generated_content": {
                "title": f"Personalized {content_type.replace('_', ' ').title()}",
                "description": "Personalized content is being generated and will be available shortly.",
                "items": ["Content generation in progress"]
            },
            "personalization_level": "basic",
            "estimated_effectiveness": 0.7,
            "implementation_notes": ["AI-generated content will be available soon"],
            "fallback_used": True
        }

    def _extract_text_from_resume(self, content: bytes, filename: str) -> str:
        """Extract text from resume file with enhanced error handling"""
        try:
            if filename.lower().endswith('.pdf'):
                # For PDF files - simplified implementation
                # In production, use PyPDF2 or pdfplumber
                try:
                    # Placeholder for PDF extraction
                    return f"PDF content from {filename} (extraction would be implemented with PyPDF2)"
                except Exception as e:
                    logger.warning(f"PDF extraction failed: {e}")
                    return "PDF content extraction failed"
                    
            elif filename.lower().endswith(('.doc', '.docx')):
                # For Word files - simplified implementation
                # In production, use python-docx
                try:
                    return f"Word document content from {filename} (extraction would be implemented with python-docx)"
                except Exception as e:
                    logger.warning(f"Word document extraction failed: {e}")
                    return "Word document extraction failed"
                    
            else:
                # For text files
                try:
                    return content.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        return content.decode('latin-1', errors='ignore')
                    except Exception as e:
                        logger.warning(f"Text extraction failed: {e}")
                        return "Text extraction failed"
                        
        except Exception as e:
            logger.error(f"File extraction failed: {str(e)}")
            return f"Unable to extract text from {filename}"

    def _track_usage(self, response, processing_time: float):
        """Enhanced usage tracking with processing time"""
        try:
            self.request_count += 1
            
            if hasattr(response, 'usage'):
                tokens_used = response.usage.total_tokens
                self.total_tokens_used += tokens_used
                
                # Calculate cost
                model = response.model
                if model in self.token_costs:
                    cost_per_1k = self.token_costs[model]["input"]
                    cost = (tokens_used / 1000) * cost_per_1k
                    self.total_cost += cost
                    
                logger.info(
                    f"AI request completed - "
                    f"Tokens: {tokens_used}, "
                    f"Cost: ${cost:.4f}, "
                    f"Time: {processing_time:.2f}s"
                )
            
        except Exception as e:
            logger.error(f"Usage tracking failed: {str(e)}")

    async def check_ai_credits(self) -> Dict[str, Any]:
        """Enhanced AI credits and usage monitoring"""
        uptime_hours = (datetime.utcnow() - self.start_time).total_seconds() / 3600
        
        return {
            "service_uptime_hours": round(uptime_hours, 2),
            "total_requests": self.request_count,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "success_rate": round((self.success_count / max(self.request_count, 1)) * 100, 2),
            "total_tokens_used": self.total_tokens_used,
            "total_cost": round(self.total_cost, 4),
            "average_cost_per_request": round(self.total_cost / max(self.request_count, 1), 4),
            "estimated_monthly_cost": round(self.total_cost * 30, 2) if uptime_hours > 0 else 0,
            "circuit_breaker_status": {
                "is_open": self._is_circuit_breaker_open(),
                "failure_count": self.circuit_breaker_failures,
                "last_failure": self.circuit_breaker_last_failure.isoformat() if self.circuit_breaker_last_failure else None
            }
        }

# Global AI service instance
ai_service = AIService()

# Convenience functions for easy importing
async def analyze_resume(content: bytes, filename: str) -> Dict[str, Any]:
    """Analyze resume - convenience function"""
    return await ai_service.analyze_resume_ai(content, filename)

async def assess_skills_ai(intern_data: Dict[str, Any]) -> Dict[str, Any]:
    """Assess skills - convenience function"""
    return await ai_service.assess_skills_ai(intern_data)

async def auto_grade_submission(
    task_data: Dict[str, Any], 
    submission_data: Dict[str, Any],
    intern_profile: Dict[str, Any]
) -> Dict[str, Any]:
    """Auto-grade submission - convenience function"""
    return await ai_service.auto_grade_submission(task_data, submission_data, intern_profile)

async def generate_personalized_content(
    content_type: str,
    user_profile: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Generate personalized content - convenience function"""
    return await ai_service.generate_personalized_content(content_type, user_profile, context)

async def get_ai_service_health() -> Dict[str, Any]:
    """Get AI service health - convenience function"""
    return await ai_service.get_ai_service_health()
