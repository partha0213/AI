import openai
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import re
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AIProcessingError, InsufficientCreditsError
from app.ai_agents.coordinator_agent import CoordinatorAgent
from app.ai_agents.assessment_agent import AssessmentAgent
from app.ai_agents.customization_agent import CustomizationAgent
from app.ai_agents.onboarding_agent import OnboardingAgent
from app.ai_agents.task_manager_agent import TaskManagerAgent
from app.ai_agents.evaluation_agent import EvaluationAgent

logger = logging.getLogger(__name__)

# Configure OpenAI
openai.api_key = settings.OPENAI_API_KEY

class AIService:
    """Central AI service for coordinating all AI operations"""
    
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

    async def analyze_resume_ai(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Analyze resume using AI"""
        try:
            # Extract text from resume (simplified - would use proper PDF/DOC parsing)
            text_content = self._extract_text_from_resume(content, filename)
            
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
            
            response = await openai.ChatCompletion.acreate(
                model=self.models["resume_analysis"],
                messages=[
                    {"role": "system", "content": "You are an expert resume analyst and career counselor."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.2
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            # Track usage
            self._track_usage(response)
            
            logger.info(f"Resume analysis completed for file: {filename}")
            return analysis
            
        except Exception as e:
            logger.error(f"Resume analysis failed: {str(e)}")
            raise AIProcessingError(f"Resume analysis failed: {str(e)}")

    async def assess_skills_ai(self, intern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess intern skills using AI"""
        try:
            assessment_prompt = f"""
            Assess the skills and capabilities of this intern based on their profile:
            
            Intern Profile:
            - Skills Listed: {intern_data.get('skills', [])}
            - Experience Level: {intern_data.get('experience_level', 'beginner')}
            - Education: {intern_data.get('education', {})}
            - Previous Experience: {intern_data.get('experience', 'None provided')}
            - Projects: {intern_data.get('projects', [])}
            
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
            
            response = await openai.ChatCompletion.acreate(
                model=self.models["skill_assessment"],
                messages=[
                    {"role": "system", "content": "You are an expert skills assessor and learning path designer for technology internships."},
                    {"role": "user", "content": assessment_prompt}
                ],
                temperature=0.3
            )
            
            assessment = json.loads(response.choices[0].message.content)
            
            # Track usage
            self._track_usage(response)
            
            logger.info("Skills assessment completed successfully")
            return assessment
            
        except Exception as e:
            logger.error(f"Skills assessment failed: {str(e)}")
            raise AIProcessingError(f"Skills assessment failed: {str(e)}")

    async def auto_grade_submission(
        self, 
        task_data: Dict[str, Any], 
        submission_data: Dict[str, Any],
        intern_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Auto-grade task submission using AI"""
        try:
            evaluation_request = {
                "type": "code_submission",  # Default, could be determined from task
                "submission_data": {
                    **submission_data,
                    "task": task_data,
                    "intern_profile": intern_profile
                }
            }
            
            # Use evaluation agent
            evaluation_result = await self.evaluation_agent.process(evaluation_request)
            
            if not evaluation_result.get("success"):
                raise AIProcessingError("Evaluation agent failed to process submission")
            
            logger.info(f"Auto-grading completed for task {task_data.get('id')}")
            return evaluation_result.get("data", {})
            
        except Exception as e:
            logger.error(f"Auto-grading failed: {str(e)}")
            raise AIProcessingError(f"Auto-grading failed: {str(e)}")

    async def generate_personalized_content(
        self, 
        content_type: str, 
        user_profile: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate personalized content using AI"""
        try:
            customization_request = {
                "type": content_type,
                "requirements": context or {},
                "intern_profile": user_profile
            }
            
            # Use customization agent
            content_result = await self.customization_agent.process(customization_request)
            
            if not content_result.get("success"):
                raise AIProcessingError("Content generation failed")
            
            logger.info(f"Personalized content generated: {content_type}")
            return content_result.get("data", {})
            
        except Exception as e:
            logger.error(f"Content generation failed: {str(e)}")
            raise AIProcessingError(f"Content generation failed: {str(e)}")

    async def recommend_next_modules(self, intern_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recommend next learning modules using AI"""
        try:
            recommendation_prompt = f"""
            Based on this intern's progress and profile, recommend the next 3-5 learning modules:
            
            Intern Progress:
            - Completed Modules: {intern_data.get('completed_modules', [])}
            - Current Skills: {intern_data.get('skills', [])}
            - Performance Scores: {intern_data.get('performance_scores', {})}
            - Learning Style: {intern_data.get('learning_style', 'visual')}
            - Program Track: {intern_data.get('program_track', 'general')}
            - Experience Level: {intern_data.get('experience_level', 'beginner')}
            
            Available Module Categories:
            - Fundamentals (HTML, CSS, JavaScript basics, Python basics)
            - Frameworks (React, Django, Flask, Node.js)
            - Databases (SQL, NoSQL, Database design)
            - Advanced Topics (APIs, Cloud, DevOps, Machine Learning)
            - Soft Skills (Communication, Project Management, Teamwork)
            
            Provide recommendations in JSON format:
            1. recommended_modules: List of 3-5 recommended modules
            2. reasoning: Why these modules are recommended
            3. learning_sequence: Optimal order to take these modules
            4. estimated_timeline: How long each module should take
            5. prerequisites_check: Any prerequisites they need to meet first
            6. difficulty_progression: How difficulty progresses through recommendations
            
            Each recommended module should include:
            - module_name: Clear, descriptive name
            - description: What they'll learn
            - difficulty: beginner/intermediate/advanced
            - estimated_hours: Time to complete
            - key_skills: Skills they'll gain
            - prerequisites: What they need to know first
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model=self.models["content_creation"],
                messages=[
                    {"role": "system", "content": "You are an expert learning path designer who creates optimal learning sequences for interns."},
                    {"role": "user", "content": recommendation_prompt}
                ],
                temperature=0.3
            )
            
            recommendations = json.loads(response.choices[0].message.content)
            
            # Track usage
            self._track_usage(response)
            
            logger.info("Module recommendations generated successfully")
            return recommendations.get("recommended_modules", [])
            
        except Exception as e:
            logger.error(f"Module recommendation failed: {str(e)}")
            raise AIProcessingError(f"Module recommendation failed: {str(e)}")

    async def generate_task_suggestions(
        self, 
        intern_profile: Dict[str, Any], 
        difficulty_level: str = "appropriate"
    ) -> List[Dict[str, Any]]:
        """Generate task suggestions using AI"""
        try:
            task_request = {
                "operation": "allocate_tasks",
                "intern_id": intern_profile.get("id"),
                "db": None  # Would need to pass actual db session
            }
            
            # Use task manager agent
            task_result = await self.task_manager_agent.process(task_request)
            
            if not task_result.get("success"):
                raise AIProcessingError("Task generation failed")
            
            suggestions = task_result.get("data", {}).get("generated_tasks", [])
            
            logger.info(f"Generated {len(suggestions)} task suggestions")
            return suggestions
            
        except Exception as e:
            logger.error(f"Task suggestion failed: {str(e)}")
            raise AIProcessingError(f"Task suggestion failed: {str(e)}")

    async def analyze_learning_progress(
        self, 
        progress_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze learning progress and provide insights"""
        try:
            analysis_prompt = f"""
            Analyze this intern's learning progress and provide actionable insights:
            
            Progress Data:
            - Completed Modules: {progress_data.get('completed_modules', 0)}
            - Total Modules: {progress_data.get('total_modules', 0)}
            - Quiz Scores: {progress_data.get('quiz_scores', [])}
            - Time Spent: {progress_data.get('time_spent_hours', 0)} hours
            - Completion Rate: {progress_data.get('completion_rate', 0)}%
            - Recent Activity: {progress_data.get('recent_activity', [])}
            - Struggle Areas: {progress_data.get('struggle_areas', [])}
            
            Provide comprehensive analysis in JSON format:
            1. progress_assessment: Overall assessment of progress
            2. learning_velocity: How quickly they're progressing
            3. engagement_level: Level of engagement with materials
            4. mastery_indicators: Signs of strong understanding
            5. concern_areas: Areas needing attention
            6. improvement_strategies: Specific strategies to improve
            7. motivation_factors: What might be motivating/demotivating them
            8. next_steps: Recommended next actions
            9. intervention_needed: Whether instructor intervention is needed
            10. predicted_outcomes: Likely outcomes if current pattern continues
            
            Be specific and actionable in recommendations.
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model=self.models["text_generation"],
                messages=[
                    {"role": "system", "content": "You are an expert learning analytics specialist who provides actionable insights on student progress."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.2
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            # Track usage
            self._track_usage(response)
            
            logger.info("Learning progress analysis completed")
            return analysis
            
        except Exception as e:
            logger.error(f"Progress analysis failed: {str(e)}")
            raise AIProcessingError(f"Progress analysis failed: {str(e)}")

    async def generate_feedback_summary(
        self, 
        feedback_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate summary of feedback using AI"""
        try:
            if not feedback_data:
                return {"summary": "No feedback available", "themes": [], "recommendations": []}
            
            feedback_texts = [f"Feedback {i+1}: {fb.get('content', '')}" for i, fb in enumerate(feedback_data)]
            
            summary_prompt = f"""
            Analyze and summarize this collection of feedback for an intern:
            
            Feedback Collection:
            {chr(10).join(feedback_texts)}
            
            Provide analysis in JSON format:
            1. overall_summary: Concise summary of all feedback
            2. common_themes: Recurring themes or patterns
            3. positive_highlights: Main positive points mentioned
            4. improvement_areas: Areas consistently mentioned for improvement
            5. sentiment_analysis: Overall sentiment (positive/neutral/negative)
            6. progress_indicators: Signs of improvement over time
            7. actionable_recommendations: Specific next steps based on feedback
            8. mentor_consistency: How consistent the feedback is
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model=self.models["text_generation"],
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing educational feedback and identifying patterns for student improvement."},
                    {"role": "user", "content": summary_prompt}
                ],
                temperature=0.2
            )
            
            summary = json.loads(response.choices[0].message.content)
            
            # Track usage
            self._track_usage(response)
            
            logger.info("Feedback summary generated successfully")
            return summary
            
        except Exception as e:
            logger.error(f"Feedback summary failed: {str(e)}")
            raise AIProcessingError(f"Feedback summary failed: {str(e)}")

    async def predict_intern_success(
        self, 
        intern_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Predict intern success probability using AI"""
        try:
            prediction_prompt = f"""
            Based on this intern's data, predict their likelihood of successful completion:
            
            Intern Data:
            - Performance Scores: {intern_data.get('performance_scores', [])}
            - Attendance Rate: {intern_data.get('attendance_rate', 0)}%
            - Task Completion Rate: {intern_data.get('task_completion_rate', 0)}%
            - Learning Progress: {intern_data.get('learning_progress', 0)}%
            - Engagement Metrics: {intern_data.get('engagement_metrics', {})}
            - Background: {intern_data.get('background', {})}
            - Time in Program: {intern_data.get('weeks_in_program', 0)} weeks
            - Program Length: {intern_data.get('total_program_weeks', 12)} weeks
            
            Provide prediction analysis in JSON format:
            1. success_probability: Probability of successful completion (0-100)
            2. confidence_level: Confidence in this prediction (0-100)
            3. key_success_indicators: Factors supporting success
            4. risk_factors: Factors that might lead to failure
            5. intervention_recommendations: Actions to improve success chances
            6. timeline_prediction: Expected timeline for key milestones
            7. areas_needing_support: Specific areas where support is needed
            8. strengths_to_leverage: Strengths that can be built upon
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model=self.models["text_generation"],
                messages=[
                    {"role": "system", "content": "You are an expert predictive analyst specializing in educational outcomes and student success prediction."},
                    {"role": "user", "content": prediction_prompt}
                ],
                temperature=0.1
            )
            
            prediction = json.loads(response.choices[0].message.content)
            
            # Track usage
            self._track_usage(response)
            
            logger.info("Success prediction completed")
            return prediction
            
        except Exception as e:
            logger.error(f"Success prediction failed: {str(e)}")
            raise AIProcessingError(f"Success prediction failed: {str(e)}")

    async def generate_improvement_plan(
        self, 
        assessment_data: Dict[str, Any], 
        target_goals: List[str]
    ) -> Dict[str, Any]:
        """Generate personalized improvement plan using AI"""
        try:
            plan_prompt = f"""
            Create a personalized improvement plan for this intern:
            
            Current Assessment:
            - Skill Levels: {assessment_data.get('skill_levels', {})}
            - Performance Areas: {assessment_data.get('performance_areas', {})}
            - Strengths: {assessment_data.get('strengths', [])}
            - Weaknesses: {assessment_data.get('weaknesses', [])}
            - Learning Style: {assessment_data.get('learning_style', 'unknown')}
            
            Target Goals:
            {chr(10).join([f"- {goal}" for goal in target_goals])}
            
            Create improvement plan in JSON format:
            1. plan_overview: Summary of the improvement strategy
            2. priority_areas: Top 3 areas to focus on first
            3. weekly_goals: Specific goals for next 4 weeks
            4. daily_activities: Suggested daily activities
            5. learning_resources: Recommended resources and materials
            6. practice_exercises: Specific exercises to build skills
            7. milestone_checkpoints: Key milestones to track progress
            8. success_metrics: How to measure improvement
            9. potential_challenges: Obstacles they might face
            10. motivation_strategies: Ways to stay motivated
            
            Make it specific, actionable, and achievable.
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model=self.models["content_creation"],
                messages=[
                    {"role": "system", "content": "You are an expert learning and development specialist who creates highly effective improvement plans for students."},
                    {"role": "user", "content": plan_prompt}
                ],
                temperature=0.3
            )
            
            plan = json.loads(response.choices[0].message.content)
            
            # Track usage
            self._track_usage(response)
            
            logger.info("Improvement plan generated successfully")
            return plan
            
        except Exception as e:
            logger.error(f"Improvement plan generation failed: {str(e)}")
            raise AIProcessingError(f"Improvement plan generation failed: {str(e)}")

    async def check_ai_credits(self) -> Dict[str, Any]:
        """Check available AI credits and usage"""
        return {
            "total_requests": self.request_count,
            "total_tokens_used": self.total_tokens_used,
            "total_cost": round(self.total_cost, 4),
            "average_cost_per_request": round(self.total_cost / max(self.request_count, 1), 4),
            "estimated_monthly_cost": round(self.total_cost * 30, 2) if self.request_count > 0 else 0
        }

    def _extract_text_from_resume(self, content: bytes, filename: str) -> str:
        """Extract text from resume file (simplified implementation)"""
        try:
            # This is a simplified implementation
            # In production, you'd use libraries like PyPDF2, python-docx, etc.
            
            if filename.lower().endswith('.pdf'):
                # For PDF files - would use PyPDF2 or pdfplumber
                return "PDF content extraction would be implemented here"
            elif filename.lower().endswith(('.doc', '.docx')):
                # For Word files - would use python-docx
                return "Word document content extraction would be implemented here"
            else:
                # For text files
                try:
                    return content.decode('utf-8')
                except:
                    return content.decode('latin-1', errors='ignore')
        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            return "Unable to extract text from resume"

    def _track_usage(self, response):
        """Track AI usage for billing and monitoring"""
        try:
            self.request_count += 1
            
            if hasattr(response, 'usage'):
                tokens_used = response.usage.total_tokens
                self.total_tokens_used += tokens_used
                
                # Calculate cost (simplified)
                model = response.model
                if model in self.token_costs:
                    cost_per_1k = self.token_costs[model]["input"]  # Simplified
                    cost = (tokens_used / 1000) * cost_per_1k
                    self.total_cost += cost
                    
                logger.info(f"AI request completed - Tokens: {tokens_used}, Cost: ${cost:.4f}")
            
        except Exception as e:
            logger.error(f"Usage tracking failed: {str(e)}")

    async def get_ai_insights_dashboard(self) -> Dict[str, Any]:
        """Get AI service insights for dashboard"""
        try:
            return {
                "service_health": "healthy",
                "total_requests": self.request_count,
                "success_rate": 95.0,  # Would calculate from actual data
                "average_response_time": 2.5,  # Would calculate from actual data
                "popular_operations": [
                    {"operation": "resume_analysis", "count": self.request_count * 0.3},
                    {"operation": "skills_assessment", "count": self.request_count * 0.25},
                    {"operation": "auto_grading", "count": self.request_count * 0.2},
                    {"operation": "content_generation", "count": self.request_count * 0.25}
                ],
                "cost_breakdown": await self.check_ai_credits(),
                "model_usage": {
                    model: {"requests": int(self.request_count * 0.3)}  # Simplified
                    for model in self.models.values()
                }
            }
        except Exception as e:
            logger.error(f"Dashboard insights failed: {str(e)}")
            return {"error": "Unable to generate insights"}

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

async def recommend_next_modules(intern_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recommend modules - convenience function"""
    return await ai_service.recommend_next_modules(intern_data)

async def assess_learning_progress(progress_data: Dict[str, Any]) -> Dict[str, Any]:
    """Assess learning progress - convenience function"""
    return await ai_service.analyze_learning_progress(progress_data)
