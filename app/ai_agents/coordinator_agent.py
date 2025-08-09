import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.ai_agents.base_agent import BaseAgent
from app.ai_agents.assessment_agent import AssessmentAgent
from app.ai_agents.customization_agent import CustomizationAgent
from app.ai_agents.onboarding_agent import OnboardingAgent
from app.ai_agents.task_manager_agent import TaskManagerAgent
from app.ai_agents.evaluation_agent import EvaluationAgent

class CoordinatorAgent(BaseAgent):
    """Central coordinator agent that orchestrates other AI agents"""
    
    def __init__(self):
        super().__init__("coordinator_agent")
        
        # Initialize other agents
        self.assessment_agent = AssessmentAgent()
        self.customization_agent = CustomizationAgent()
        self.onboarding_agent = OnboardingAgent()
        self.task_manager_agent = TaskManagerAgent()
        self.evaluation_agent = EvaluationAgent()
        
        # Agent workflow definitions
        self.workflows = {
            "new_intern_onboarding": [
                {"agent": "onboarding", "operation": "create_profile"},
                {"agent": "assessment", "operation": "resume_analysis"},
                {"agent": "assessment", "operation": "skill_assessment"},
                {"agent": "customization", "operation": "learning_path"},
                {"agent": "task_manager", "operation": "allocate_tasks"}
            ],
            "task_submission_processing": [
                {"agent": "evaluation", "operation": "evaluate_submission"},
                {"agent": "task_manager", "operation": "update_progress"},
                {"agent": "customization", "operation": "recommend_next"}
            ],
            "periodic_review": [
                {"agent": "assessment", "operation": "progress_assessment"},
                {"agent": "task_manager", "operation": "monitor_progress"},
                {"agent": "customization", "operation": "update_learning_path"}
            ]
        }
        
        # Agent communication log
        self.communication_log = []
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process coordinated workflow requests"""
        workflow_type = data.get("workflow")
        
        if workflow_type == "new_intern_onboarding":
            return await self.execute_onboarding_workflow(data)
        elif workflow_type == "task_submission_processing":
            return await self.execute_submission_workflow(data)
        elif workflow_type == "periodic_review":
            return await self.execute_review_workflow(data)
        elif workflow_type == "comprehensive_evaluation":
            return await self.execute_comprehensive_evaluation(data)
        elif workflow_type == "adaptive_learning_update":
            return await self.execute_adaptive_learning_update(data)
        else:
            return self.format_response(
                False,
                None,
                "Invalid workflow type"
            )
    
    async def execute_onboarding_workflow(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute complete onboarding workflow for new intern"""
        try:
            intern_data = data.get("intern_data")
            db = data.get("db")
            
            workflow_result = {
                "workflow": "new_intern_onboarding",
                "steps_completed": [],
                "results": {},
                "recommendations": {},
                "next_actions": []
            }
            
            # Step 1: Profile Creation (Onboarding Agent)
            self.log_activity("workflow_step", {"step": "profile_creation", "agent": "onboarding"})
            
            profile_result = await self.onboarding_agent.process({
                "type": "create_profile",
                "intern_data": intern_data
            })
            
            workflow_result["steps_completed"].append("profile_creation")
            workflow_result["results"]["profile"] = profile_result
            
            if not profile_result.get("success"):
                return self.format_response(False, workflow_result, "Profile creation failed")
            
            # Step 2: Resume Analysis (Assessment Agent)
            if intern_data.get("resume_file"):
                self.log_activity("workflow_step", {"step": "resume_analysis", "agent": "assessment"})
                
                resume_result = await self.assessment_agent.process({
                    "type": "resume_analysis",
                    "file_content": intern_data["resume_file"]
                })
                
                workflow_result["steps_completed"].append("resume_analysis")
                workflow_result["results"]["resume_analysis"] = resume_result
                
                # Update intern data with resume insights
                if resume_result.get("success"):
                    intern_data.update(resume_result.get("data", {}))
            
            # Step 3: Skill Assessment (Assessment Agent)
            self.log_activity("workflow_step", {"step": "skill_assessment", "agent": "assessment"})
            
            skill_result = await self.assessment_agent.process({
                "type": "skill_assessment",
                "intern_data": intern_data
            })
            
            workflow_result["steps_completed"].append("skill_assessment")
            workflow_result["results"]["skill_assessment"] = skill_result
            
            if skill_result.get("success"):
                intern_data.update(skill_result.get("data", {}))
            
            # Step 4: Learning Path Generation (Customization Agent)
            self.log_activity("workflow_step", {"step": "learning_path", "agent": "customization"})
            
            learning_path_result = await self.customization_agent.process({
                "type": "learning_path",
                "intern_profile": intern_data
            })
            
            workflow_result["steps_completed"].append("learning_path")
            workflow_result["results"]["learning_path"] = learning_path_result
            
            # Step 5: Initial Task Allocation (Task Manager Agent)
            self.log_activity("workflow_step", {"step": "task_allocation", "agent": "task_manager"})
            
            task_allocation_result = await self.task_manager_agent.process({
                "operation": "allocate_tasks",
                "intern_id": intern_data.get("id"),
                "db": db
            })
            
            workflow_result["steps_completed"].append("task_allocation")
            workflow_result["results"]["task_allocation"] = task_allocation_result
            
            # Generate comprehensive recommendations
            workflow_result["recommendations"] = await self._generate_onboarding_recommendations(
                workflow_result["results"]
            )
            
            # Define next actions
            workflow_result["next_actions"] = [
                "Send welcome email to intern",
                "Schedule orientation meeting with mentor",
                "Provide access to learning platform",
                "Set up development environment",
                "Schedule first check-in meeting"
            ]
            
            self.log_activity("onboarding_workflow_completed", {
                "intern_id": intern_data.get("id"),
                "steps_completed": len(workflow_result["steps_completed"]),
                "success": True
            })
            
            return self.format_response(
                True,
                workflow_result,
                f"Onboarding workflow completed successfully with {len(workflow_result['steps_completed'])} steps"
            )
            
        except Exception as e:
            self.logger.error(f"Onboarding workflow failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Onboarding workflow failed: {str(e)}"
            )
    
    async def execute_submission_workflow(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task submission processing workflow"""
        try:
            submission_data = data.get("submission_data")
            task_id = data.get("task_id")
            intern_id = data.get("intern_id")
            db = data.get("db")
            
            workflow_result = {
                "workflow": "task_submission_processing",
                "steps_completed": [],
                "results": {},
                "feedback": {},
                "next_steps": []
            }
            
            # Step 1: Evaluate Submission (Evaluation Agent)
            self.log_activity("workflow_step", {"step": "evaluation", "agent": "evaluation"})
            
            evaluation_type = self._determine_evaluation_type(submission_data)
            evaluation_result = await self.evaluation_agent.process({
                "type": evaluation_type,
                "submission_data": submission_data
            })
            
            workflow_result["steps_completed"].append("evaluation")
            workflow_result["results"]["evaluation"] = evaluation_result
            
            # Step 2: Update Task Progress (Task Manager Agent)
            self.log_activity("workflow_step", {"step": "progress_update", "agent": "task_manager"})
            
            progress_result = await self.task_manager_agent.process({
                "operation": "monitor_progress",
                "task_ids": [task_id],
                "db": db
            })
            
            workflow_result["steps_completed"].append("progress_update")
            workflow_result["results"]["progress_update"] = progress_result
            
            # Step 3: Generate Next Recommendations (Customization Agent)
            if evaluation_result.get("success"):
                self.log_activity("workflow_step", {"step": "next_recommendations", "agent": "customization"})
                
                recommendations_result = await self.customization_agent.process({
                    "type": "task_customization",
                    "task_data": {"evaluation": evaluation_result.get("data")},
                    "intern_profile": submission_data.get("intern_profile", {})
                })
                
                workflow_result["steps_completed"].append("next_recommendations")
                workflow_result["results"]["next_recommendations"] = recommendations_result
            
            # Generate integrated feedback
            workflow_result["feedback"] = await self._generate_integrated_feedback(
                evaluation_result,
                workflow_result["results"]
            )
            
            # Determine next steps
            workflow_result["next_steps"] = await self._determine_next_steps(
                evaluation_result,
                submission_data.get("intern_profile", {})
            )
            
            self.log_activity("submission_workflow_completed", {
                "task_id": task_id,
                "intern_id": intern_id,
                "evaluation_score": evaluation_result.get("data", {}).get("overall_score", 0),
                "steps_completed": len(workflow_result["steps_completed"])
            })
            
            return self.format_response(
                True,
                workflow_result,
                "Submission processing workflow completed successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Submission workflow failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Submission workflow failed: {str(e)}"
            )
    
    async def execute_comprehensive_evaluation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute comprehensive evaluation across all agents"""
        try:
            intern_id = data.get("intern_id")
            evaluation_period = data.get("period", "monthly")  # weekly, monthly, quarterly
            db = data.get("db")
            
            comprehensive_result = {
                "evaluation_type": "comprehensive",
                "period": evaluation_period,
                "intern_id": intern_id,
                "agent_evaluations": {},
                "integrated_insights": {},
                "action_plan": {}
            }
            
            # Gather data from all agents
            agent_tasks = [
                ("assessment", self.assessment_agent.process({
                    "type": "skill_assessment",
                    "intern_data": {"id": intern_id}
                })),
                ("task_manager", self.task_manager_agent.process({
                    "operation": "monitor_progress",
                    "intern_id": intern_id,
                    "db": db
                })),
                ("customization", self.customization_agent.process({
                    "type": "learning_path",
                    "intern_profile": {"intern_id": intern_id}
                }))
            ]
            
            # Execute all agent evaluations concurrently
            results = await asyncio.gather(*[task[1] for task in agent_tasks], return_exceptions=True)
            
            # Process results
            for i, (agent_name, _) in enumerate(agent_tasks):
                if not isinstance(results[i], Exception):
                    comprehensive_result["agent_evaluations"][agent_name] = results[i]
                else:
                    self.logger.error(f"Agent {agent_name} evaluation failed: {results[i]}")
            
            # Generate integrated insights
            comprehensive_result["integrated_insights"] = await self._generate_integrated_insights(
                comprehensive_result["agent_evaluations"]
            )
            
            # Create action plan
            comprehensive_result["action_plan"] = await self._create_comprehensive_action_plan(
                comprehensive_result["integrated_insights"]
            )
            
            self.log_activity("comprehensive_evaluation_completed", {
                "intern_id": intern_id,
                "period": evaluation_period,
                "agents_evaluated": len(comprehensive_result["agent_evaluations"])
            })
            
            return self.format_response(
                True,
                comprehensive_result,
                "Comprehensive evaluation completed successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Comprehensive evaluation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Comprehensive evaluation failed: {str(e)}"
            )
    
    async def get_agent_communication_log(self) -> List[Dict[str, Any]]:
        """Get log of inter-agent communications"""
        return self.communication_log[-100:]  # Return last 100 communications
    
    async def _generate_onboarding_recommendations(self, workflow_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive onboarding recommendations"""
        recommendations = {
            "immediate_actions": [],
            "first_week_goals": [],
            "first_month_objectives": [],
            "potential_challenges": [],
            "success_indicators": []
        }
        
        # Analyze results from each step
        skill_data = workflow_results.get("skill_assessment", {}).get("data", {})
        learning_path = workflow_results.get("learning_path", {}).get("data", {})
        task_allocation = workflow_results.get("task_allocation", {}).get("data", {})
        
        # Generate recommendations based on combined data
        if skill_data.get("experience_level") == "Beginner":
            recommendations["immediate_actions"].extend([
                "Assign introductory learning modules",
                "Pair with experienced mentor",
                "Provide comprehensive onboarding materials"
            ])
        
        if learning_path.get("complexity_score", 0) > 7:
            recommendations["potential_challenges"].append(
                "High learning path complexity - monitor closely for overwhelm"
            )
        
        return recommendations
    
    async def _generate_integrated_feedback(
        self, 
        evaluation_result: Dict[str, Any], 
        workflow_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate integrated feedback from multiple agent results"""
        
        feedback = {
            "overall_assessment": "",
            "key_strengths": [],
            "priority_improvements": [],
            "personalized_recommendations": [],
            "mentor_guidance": []
        }
        
        if evaluation_result.get("success"):
            eval_data = evaluation_result.get("data", {})
            overall_score = eval_data.get("overall_score", 0)
            
            if overall_score >= 85:
                feedback["overall_assessment"] = "Excellent work! You're exceeding expectations."
            elif overall_score >= 70:
                feedback["overall_assessment"] = "Good progress! You're meeting most requirements."
            elif overall_score >= 60:
                feedback["overall_assessment"] = "Adequate work, but there's room for improvement."
            else:
                feedback["overall_assessment"] = "Needs significant improvement to meet standards."
            
            feedback["key_strengths"] = eval_data.get("strengths", [])
            feedback["priority_improvements"] = eval_data.get("areas_for_improvement", [])
        
        return feedback
    
    def _determine_evaluation_type(self, submission_data: Dict[str, Any]) -> str:
        """Determine the appropriate evaluation type based on submission"""
        
        if submission_data.get("code_files"):
            return "code_submission"
        elif submission_data.get("project_info"):
            return "project_submission"
        elif submission_data.get("content") and len(submission_data["content"]) > 500:
            return "written_assignment"
        elif submission_data.get("presentation_materials"):
            return "presentation"
        else:
            return "code_submission"  # Default
    
    def log_inter_agent_communication(
        self, 
        from_agent: str, 
        to_agent: str, 
        message_type: str, 
        data: Dict[str, Any]
    ):
        """Log communication between agents"""
        communication = {
            "timestamp": datetime.utcnow().isoformat(),
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message_type": message_type,
            "data_summary": {k: str(v)[:100] for k, v in data.items()},
            "success": True
        }
        
        self.communication_log.append(communication)
        
        # Keep only last 1000 communications to prevent memory issues
        if len(self.communication_log) > 1000:
            self.communication_log = self.communication_log[-1000:]
