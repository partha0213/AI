import openai
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.ai_agents.base_agent import BaseAgent
from app.core.config import settings
from app.models.intern import Intern
from app.models.mentor import Mentor
from app.models.task import Task, TaskStatus, TaskPriority
from app.services.task_service import create_task, update_task
from app.services.notification_service import notification_service

openai.api_key = settings.OPENAI_API_KEY

class TaskManagerAgent(BaseAgent):
    """AI agent for intelligent task allocation, monitoring, and management"""
    
    def __init__(self):
        super().__init__("task_manager_agent")
        self.task_templates = {
            "web_development": [
                {"type": "frontend", "difficulty": "beginner", "estimated_hours": 8},
                {"type": "backend", "difficulty": "intermediate", "estimated_hours": 12},
                {"type": "fullstack", "difficulty": "advanced", "estimated_hours": 20}
            ],
            "data_science": [
                {"type": "analysis", "difficulty": "beginner", "estimated_hours": 6},
                {"type": "modeling", "difficulty": "intermediate", "estimated_hours": 15},
                {"type": "deployment", "difficulty": "advanced", "estimated_hours": 18}
            ]
        }
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process task management request"""
        operation = data.get("operation")
        
        if operation == "allocate_tasks":
            return await self.allocate_tasks_intelligently(data.get("intern_id"), data.get("db"))
        elif operation == "generate_task":
            return await self.generate_custom_task(data.get("requirements"))
        elif operation == "monitor_progress":
            return await self.monitor_task_progress(data.get("task_ids"), data.get("db"))
        elif operation == "rebalance_workload":
            return await self.rebalance_workload(data.get("mentor_id"), data.get("db"))
        elif operation == "predict_completion":
            return await self.predict_task_completion(data.get("task_id"), data.get("db"))
        else:
            return self.format_response(
                False,
                None,
                "Invalid task management operation"
            )
    
    async def allocate_tasks_intelligently(self, intern_id: int, db: Session) -> Dict[str, Any]:
        """Intelligently allocate tasks based on intern profile and current workload"""
        try:
            # Get intern profile
            intern = db.query(Intern).filter(Intern.id == intern_id).first()
            if not intern:
                return self.format_response(False, None, "Intern not found")
            
            # Analyze intern's current workload and performance
            current_tasks = db.query(Task).filter(
                and_(
                    Task.assigned_intern_id == intern_id,
                    Task.status.in_(["assigned", "in_progress"])
                )
            ).all()
            
            workload_analysis = await self._analyze_current_workload(intern, current_tasks)
            
            # Generate task allocation strategy
            allocation_prompt = f"""
            Based on the intern profile and current workload, suggest optimal task allocation:
            
            Intern Profile:
            - Experience Level: {intern.experience_level}
            - Skills: {intern.skills}
            - Program Track: {intern.program_track}
            - Performance Score: {intern.performance_score}
            - Learning Style: {intern.learning_style}
            
            Current Workload Analysis:
            - Active Tasks: {len(current_tasks)}
            - Estimated Hours Remaining: {workload_analysis.get('hours_remaining', 0)}
            - Difficulty Distribution: {workload_analysis.get('difficulty_distribution', {})}
            - Performance Trend: {workload_analysis.get('performance_trend', 'stable')}
            
            Available Time Capacity: {workload_analysis.get('available_capacity', 20)} hours/week
            
            Provide task allocation recommendations in JSON format:
            1. recommended_tasks: List of task suggestions with type, difficulty, priority
            2. optimal_schedule: Weekly distribution of tasks
            3. skill_focus_areas: Skills to emphasize in upcoming tasks
            4. workload_balance: Assessment of current workload balance
            5. next_task_timing: When to assign next task
            6. risk_factors: Potential challenges to watch for
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert task allocation manager for internship programs."},
                    {"role": "user", "content": allocation_prompt}
                ],
                temperature=0.3
            )
            
            allocation_strategy = json.loads(response.choices[0].message.content)
            
            # Generate specific tasks based on recommendations
            generated_tasks = []
            for task_rec in allocation_strategy.get("recommended_tasks", [])[:3]:  # Limit to 3 tasks
                task_details = await self._generate_specific_task(intern, task_rec)
                if task_details:
                    generated_tasks.append(task_details)
            
            self.log_activity("tasks_allocated", {
                "intern_id": intern_id,
                "tasks_generated": len(generated_tasks),
                "workload_balance": allocation_strategy.get("workload_balance")
            })
            
            return self.format_response(
                True,
                {
                    "allocation_strategy": allocation_strategy,
                    "generated_tasks": generated_tasks,
                    "workload_analysis": workload_analysis
                },
                f"Successfully generated {len(generated_tasks)} task recommendations"
            )
            
        except Exception as e:
            self.logger.error(f"Task allocation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Task allocation failed: {str(e)}"
            )
    
    async def generate_custom_task(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Generate custom task based on specific requirements"""
        try:
            task_prompt = f"""
            Generate a detailed internship task based on these requirements:
            
            Requirements:
            - Subject Area: {requirements.get('subject_area', 'General')}
            - Difficulty Level: {requirements.get('difficulty', 'Intermediate')}
            - Estimated Duration: {requirements.get('duration_hours', 8)} hours
            - Skills to Practice: {requirements.get('skills', [])}
            - Learning Objectives: {requirements.get('learning_objectives', [])}
            - Deliverables Expected: {requirements.get('deliverables', [])}
            - Tools/Technologies: {requirements.get('tools', [])}
            
            Create a comprehensive task in JSON format:
            1. title: Engaging and descriptive task title
            2. description: Detailed task description
            3. instructions: Step-by-step instructions
            4. requirements: Technical and functional requirements
            5. deliverables: Expected outputs and formats
            6. evaluation_criteria: How the task will be assessed
            7. resources: Helpful learning materials and references
            8. milestones: Key checkpoints during task completion
            9. bonus_challenges: Optional advanced features
            10. estimated_timeline: Breakdown of time allocation
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert task designer for technical internships."},
                    {"role": "user", "content": task_prompt}
                ],
                temperature=0.4
            )
            
            task_details = json.loads(response.choices[0].message.content)
            
            # Add metadata
            task_details["generated_at"] = datetime.utcnow().isoformat()
            task_details["requirements_met"] = requirements
            task_details["complexity_score"] = self._calculate_task_complexity(requirements)
            
            self.log_activity("custom_task_generated", {
                "subject_area": requirements.get('subject_area'),
                "difficulty": requirements.get('difficulty'),
                "complexity_score": task_details["complexity_score"]
            })
            
            return self.format_response(
                True,
                task_details,
                "Custom task generated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Custom task generation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Custom task generation failed: {str(e)}"
            )
    
    async def monitor_task_progress(self, task_ids: List[int], db: Session) -> Dict[str, Any]:
        """Monitor and analyze task progress across multiple tasks"""
        try:
            tasks = db.query(Task).filter(Task.id.in_(task_ids)).all()
            if not tasks:
                return self.format_response(False, None, "No tasks found")
            
            progress_analysis = {
                "total_tasks": len(tasks),
                "status_distribution": {},
                "overdue_tasks": [],
                "at_risk_tasks": [],
                "performance_insights": {},
                "recommendations": []
            }
            
            # Analyze each task
            for task in tasks:
                # Status distribution
                status = task.status
                progress_analysis["status_distribution"][status] = \
                    progress_analysis["status_distribution"].get(status, 0) + 1
                
                # Check for overdue tasks
                if task.due_date and task.due_date < datetime.utcnow() and task.status != "completed":
                    progress_analysis["overdue_tasks"].append({
                        "task_id": task.id,
                        "title": task.title,
                        "days_overdue": (datetime.utcnow() - task.due_date).days,
                        "assigned_intern": task.assigned_intern_id
                    })
                
                # Identify at-risk tasks
                risk_score = await self._calculate_task_risk_score(task, db)
                if risk_score > 0.7:
                    progress_analysis["at_risk_tasks"].append({
                        "task_id": task.id,
                        "title": task.title,
                        "risk_score": risk_score,
                        "risk_factors": await self._identify_risk_factors(task, db)
                    })
            
            # Generate AI insights and recommendations
            insights_prompt = f"""
            Analyze this task progress data and provide insights:
            
            Task Progress Summary:
            - Total Tasks: {len(tasks)}
            - Status Distribution: {progress_analysis['status_distribution']}
            - Overdue Tasks: {len(progress_analysis['overdue_tasks'])}
            - At-Risk Tasks: {len(progress_analysis['at_risk_tasks'])}
            
            Provide analysis in JSON format:
            1. overall_health: Assessment of overall progress health
            2. key_issues: Main problems identified
            3. performance_trends: Observable trends in task completion
            4. recommendations: Specific actionable recommendations
            5. intervention_needed: Tasks requiring immediate attention
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert project management analyst."},
                    {"role": "user", "content": insights_prompt}
                ],
                temperature=0.2
            )
            
            ai_insights = json.loads(response.choices[0].message.content)
            progress_analysis["ai_insights"] = ai_insights
            
            self.log_activity("progress_monitored", {
                "tasks_analyzed": len(tasks),
                "overdue_count": len(progress_analysis["overdue_tasks"]),
                "at_risk_count": len(progress_analysis["at_risk_tasks"])
            })
            
            return self.format_response(
                True,
                progress_analysis,
                f"Analyzed progress for {len(tasks)} tasks"
            )
            
        except Exception as e:
            self.logger.error(f"Progress monitoring failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Progress monitoring failed: {str(e)}"
            )
    
    async def predict_task_completion(self, task_id: int, db: Session) -> Dict[str, Any]:
        """Predict task completion time and likelihood of success"""
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return self.format_response(False, None, "Task not found")
            
            # Get intern and historical data
            intern = db.query(Intern).filter(Intern.id == task.assigned_intern_id).first()
            if not intern:
                return self.format_response(False, None, "Intern not found")
            
            # Analyze historical performance
            historical_tasks = db.query(Task).filter(
                and_(
                    Task.assigned_intern_id == intern.id,
                    Task.status == "completed"
                )
            ).all()
            
            historical_analysis = self._analyze_historical_performance(historical_tasks)
            
            # Current task analysis
            current_progress = {
                "status": task.status,
                "time_elapsed": self._calculate_time_elapsed(task),
                "estimated_remaining": task.estimated_hours - (task.progress_percentage / 100 * task.estimated_hours),
                "progress_percentage": task.progress_percentage
            }
            
            # Prediction model
            prediction_prompt = f"""
            Predict task completion based on this data:
            
            Current Task:
            - Title: {task.title}
            - Difficulty: {task.difficulty_level}
            - Estimated Hours: {task.estimated_hours}
            - Current Progress: {task.progress_percentage}%
            - Status: {task.status}
            - Time Elapsed: {current_progress['time_elapsed']} hours
            
            Intern Profile:
            - Experience Level: {intern.experience_level}
            - Performance Score: {intern.performance_score}
            - Skills Match: {self._calculate_skills_match(task, intern)}
            
            Historical Performance:
            - Average Completion Time: {historical_analysis.get('avg_completion_time', 0)} hours
            - On-time Completion Rate: {historical_analysis.get('ontime_rate', 0)}%
            - Average Score: {historical_analysis.get('avg_score', 0)}
            
            Provide prediction in JSON format:
            1. completion_probability: Likelihood of successful completion (0-100%)
            2. estimated_completion_date: Predicted completion date
            3. confidence_score: Confidence in prediction (0-100%)
            4. risk_factors: Factors that might delay completion
            5. success_factors: Factors supporting completion
            6. recommended_actions: Interventions to improve chances
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert in project completion prediction and risk analysis."},
                    {"role": "user", "content": prediction_prompt}
                ],
                temperature=0.1
            )
            
            prediction = json.loads(response.choices[0].message.content)
            
            # Add technical metrics
            prediction["technical_metrics"] = {
                "historical_analysis": historical_analysis,
                "current_progress": current_progress,
                "skills_match": self._calculate_skills_match(task, intern),
                "complexity_factor": self._calculate_task_complexity_factor(task)
            }
            
            self.log_activity("completion_predicted", {
                "task_id": task_id,
                "completion_probability": prediction.get("completion_probability"),
                "confidence_score": prediction.get("confidence_score")
            })
            
            return self.format_response(
                True,
                prediction,
                "Task completion prediction generated"
            )
            
        except Exception as e:
            self.logger.error(f"Completion prediction failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Completion prediction failed: {str(e)}"
            )
    
    async def _analyze_current_workload(self, intern: Intern, current_tasks: List[Task]) -> Dict[str, Any]:
        """Analyze intern's current workload"""
        total_hours = sum(task.estimated_hours or 0 for task in current_tasks)
        completed_hours = sum(
            (task.progress_percentage / 100) * (task.estimated_hours or 0) 
            for task in current_tasks
        )
        
        difficulty_distribution = {}
        for task in current_tasks:
            diff = task.difficulty_level or "medium"
            difficulty_distribution[diff] = difficulty_distribution.get(diff, 0) + 1
        
        return {
            "total_active_tasks": len(current_tasks),
            "total_estimated_hours": total_hours,
            "completed_hours": completed_hours,
            "hours_remaining": total_hours - completed_hours,
            "difficulty_distribution": difficulty_distribution,
            "available_capacity": max(0, 40 - total_hours),  # Assuming 40 hours/week capacity
            "performance_trend": self._calculate_performance_trend(intern)
        }
    
    def _calculate_task_complexity(self, requirements: Dict[str, Any]) -> int:
        """Calculate task complexity score (1-10)"""
        complexity = 3  # Base complexity
        
        difficulty_map = {"beginner": 1, "intermediate": 2, "advanced": 3}
        complexity += difficulty_map.get(requirements.get("difficulty", "intermediate"), 2)
        
        # Adjust for duration
        hours = requirements.get("duration_hours", 8)
        if hours > 20:
            complexity += 3
        elif hours > 10:
            complexity += 2
        elif hours > 5:
            complexity += 1
        
        # Adjust for skills count
        skills_count = len(requirements.get("skills", []))
        complexity += min(skills_count // 2, 3)
        
        return min(complexity, 10)
    
    async def _generate_specific_task(self, intern: Intern, task_recommendation: Dict[str, Any]) -> Dict[str, Any]:
        """Generate specific task details based on recommendation"""
        # This would use the generate_custom_task method with intern-specific requirements
        requirements = {
            "subject_area": intern.program_track,
            "difficulty": task_recommendation.get("difficulty", "intermediate"),
            "duration_hours": task_recommendation.get("estimated_hours", 8),
            "skills": intern.skills[:3] if intern.skills else [],
            "learning_objectives": [f"Practice {skill}" for skill in (intern.skills[:2] if intern.skills else [])],
            "tools": ["VS Code", "Git", "Browser Developer Tools"]
        }
        
        return await self.generate_custom_task(requirements)
