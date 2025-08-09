import openai
import json
from typing import Dict, Any, List

from app.ai_agents.base_agent import BaseAgent
from app.core.config import settings

openai.api_key = settings.OPENAI_API_KEY

class CustomizationAgent(BaseAgent):
    """AI agent for generating personalized learning paths and project plans"""
    
    def __init__(self):
        super().__init__("customization_agent")
        self.learning_tracks = {
            "web_development": {
                "modules": ["HTML/CSS", "JavaScript", "React", "Node.js", "Database"],
                "duration_weeks": 12
            },
            "data_science": {
                "modules": ["Python", "Statistics", "Machine Learning", "Data Visualization", "SQL"],
                "duration_weeks": 16
            },
            "mobile_development": {
                "modules": ["Mobile Fundamentals", "React Native", "API Integration", "Testing", "Deployment"],
                "duration_weeks": 14
            }
        }
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process customization request"""
        customization_type = data.get("type")
        
        if customization_type == "learning_path":
            return await self.generate_learning_path(data.get("intern_profile"))
        elif customization_type == "project_plan":
            return await self.generate_project_plan(data.get("requirements"))
        elif customization_type == "task_customization":
            return await self.customize_task(data.get("task_data"), data.get("intern_profile"))
        else:
            return self.format_response(
                False,
                None,
                "Invalid customization type"
            )
    
    async def generate_learning_path(self, intern_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Generate personalized learning path"""
        try:
            customization_prompt = f"""
            Create a personalized learning path for this intern:
            
            Intern Profile:
            - Current Skills: {intern_profile.get('skills', [])}
            - Experience Level: {intern_profile.get('experience_level', 'Beginner')}
            - Preferred Track: {intern_profile.get('program_track', 'General')}
            - Learning Style: {intern_profile.get('learning_style', 'Mixed')}
            - Assessment Score: {intern_profile.get('assessment_score', 0)}
            - Strengths: {intern_profile.get('strengths', [])}
            - Improvement Areas: {intern_profile.get('improvement_areas', [])}
            
            Generate a learning path in JSON format with:
            1. modules: Array of learning modules with title, description, duration, prerequisites
            2. timeline: Suggested timeline in weeks
            3. milestones: Key milestones and checkpoints
            4. resources: Recommended learning resources
            5. assessments: Periodic assessments and quizzes
            6. projects: Hands-on projects for each module
            7. difficulty_progression: How difficulty increases over time
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert learning path designer for technical internships."},
                    {"role": "user", "content": customization_prompt}
                ],
                temperature=0.3
            )
            
            learning_path = json.loads(response.choices[0].message.content)
            
            # Add metadata
            learning_path["generated_for"] = intern_profile.get("intern_id")
            learning_path["created_at"] = self.created_at.isoformat()
            learning_path["customization_level"] = self._calculate_customization_level(intern_profile)
            
            self.log_activity("learning_path_generated", {
                "intern_id": intern_profile.get("intern_id"),
                "track": intern_profile.get("program_track"),
                "modules_count": len(learning_path.get("modules", []))
            })
            
            return self.format_response(
                True,
                learning_path,
                "Learning path generated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Learning path generation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Learning path generation failed: {str(e)}"
            )
    
    async def generate_project_plan(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed project plan"""
        try:
            project_prompt = f"""
            Create a comprehensive project plan based on these requirements:
            
            Requirements:
            - Project Type: {requirements.get('project_type')}
            - Duration: {requirements.get('duration_weeks', 4)} weeks
            - Skill Level: {requirements.get('skill_level', 'Intermediate')}
            - Technologies: {requirements.get('technologies', [])}
            - Team Size: {requirements.get('team_size', 1)}
            - Learning Objectives: {requirements.get('learning_objectives', [])}
            
            Generate a project plan in JSON format with:
            1. project_overview: Title, description, objectives
            2. phases: Project phases with tasks, deliverables, timelines
            3. technical_requirements: Tech stack, tools, frameworks
            4. milestones: Key deliverables and deadlines
            5. resources: Learning resources, documentation, tutorials
            6. evaluation_criteria: How the project will be assessed
            7. risk_mitigation: Potential challenges and solutions
            8. bonus_features: Optional advanced features
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert project manager for technical internships."},
                    {"role": "user", "content": project_prompt}
                ],
                temperature=0.4
            )
            
            project_plan = json.loads(response.choices[0].message.content)
            
            # Add metadata
            project_plan["generated_at"] = self.created_at.isoformat()
            project_plan["complexity_score"] = self._calculate_project_complexity(requirements)
            
            self.log_activity("project_plan_generated", {
                "project_type": requirements.get("project_type"),
                "duration": requirements.get("duration_weeks"),
                "phases_count": len(project_plan.get("phases", []))
            })
            
            return self.format_response(
                True,
                project_plan,
                "Project plan generated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Project plan generation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Project plan generation failed: {str(e)}"
            )
    
    async def customize_task(self, task_data: Dict[str, Any], intern_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Customize task based on intern's profile"""
        try:
            customization_prompt = f"""
            Customize this task for the specific intern:
            
            Original Task:
            - Title: {task_data.get('title')}
            - Description: {task_data.get('description')}
            - Difficulty: {task_data.get('difficulty_level', 'Medium')}
            - Estimated Hours: {task_data.get('estimated_hours', 8)}
            
            Intern Profile:
            - Experience Level: {intern_profile.get('experience_level')}
            - Skills: {intern_profile.get('skills', [])}
            - Learning Style: {intern_profile.get('learning_style', 'Mixed')}
            - Previous Performance: {intern_profile.get('performance_score', 0)}
            
            Provide customized task in JSON format with:
            1. customized_description: Tailored task description
            2. difficulty_adjustment: Adjusted difficulty level
            3. personalized_hints: Specific hints based on intern's profile
            4. additional_resources: Relevant learning materials
            5. success_criteria: Clear success metrics
            6. estimated_time: Adjusted time estimate
            7. bonus_challenges: Optional advanced challenges
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert task customizer for personalized learning."},
                    {"role": "user", "content": customization_prompt}
                ],
                temperature=0.3
            )
            
            customized_task = json.loads(response.choices[0].message.content)
            
            # Add original task reference
            customized_task["original_task_id"] = task_data.get("id")
            customized_task["customized_for"] = intern_profile.get("intern_id")
            
            self.log_activity("task_customized", {
                "task_id": task_data.get("id"),
                "intern_id": intern_profile.get("intern_id"),
                "difficulty_adjustment": customized_task.get("difficulty_adjustment")
            })
            
            return self.format_response(
                True,
                customized_task,
                "Task customized successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Task customization failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Task customization failed: {str(e)}"
            )
    
    def _calculate_customization_level(self, intern_profile: Dict[str, Any]) -> str:
        """Calculate level of customization needed"""
        score = intern_profile.get("assessment_score", 0)
        experience = intern_profile.get("experience_level", "Beginner")
        
        if score >= 80 and experience == "Advanced":
            return "Minimal"
        elif score >= 60 and experience in ["Intermediate", "Advanced"]:
            return "Moderate"
        else:
            return "High"
    
    def _calculate_project_complexity(self, requirements: Dict[str, Any]) -> int:
        """Calculate project complexity score (1-10)"""
        complexity
