import openai
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.ai_agents.base_agent import BaseAgent
from app.core.config import settings

openai.api_key = settings.OPENAI_API_KEY

class EvaluationAgent(BaseAgent):
    """AI agent for intelligent evaluation and grading of intern submissions"""
    
    def __init__(self):
        super().__init__("evaluation_agent")
        self.evaluation_criteria = {
            "code_quality": {
                "weight": 0.3,
                "factors": ["readability", "structure", "best_practices", "comments"]
            },
            "functionality": {
                "weight": 0.35,
                "factors": ["correctness", "completeness", "edge_cases", "performance"]
            },
            "creativity": {
                "weight": 0.15,
                "factors": ["innovation", "problem_solving", "unique_approach"]
            },
            "documentation": {
                "weight": 0.2,
                "factors": ["clarity", "completeness", "examples", "formatting"]
            }
        }
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process evaluation request"""
        evaluation_type = data.get("type")
        
        if evaluation_type == "code_submission":
            return await self.evaluate_code_submission(data.get("submission_data"))
        elif evaluation_type == "project_submission":
            return await self.evaluate_project_submission(data.get("submission_data"))
        elif evaluation_type == "written_assignment":
            return await self.evaluate_written_assignment(data.get("submission_data"))
        elif evaluation_type == "presentation":
            return await self.evaluate_presentation(data.get("submission_data"))
        elif evaluation_type == "peer_evaluation":
            return await self.process_peer_evaluation(data.get("evaluation_data"))
        else:
            return self.format_response(
                False,
                None,
                "Invalid evaluation type"
            )
    
    async def evaluate_code_submission(self, submission_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate code submission with detailed analysis"""
        try:
            task = submission_data.get("task")
            code_files = submission_data.get("code_files", [])
            intern_profile = submission_data.get("intern_profile", {})
            
            # Analyze each code file
            file_analyses = []
            for file_info in code_files:
                file_analysis = await self._analyze_code_file(
                    file_info.get("filename", ""),
                    file_info.get("content", ""),
                    file_info.get("language", "")
                )
                file_analyses.append(file_analysis)
            
            # Overall evaluation
            evaluation_prompt = f"""
            Evaluate this code submission comprehensively:
            
            Task Requirements:
            - Title: {task.get('title', '')}
            - Description: {task.get('description', '')}
            - Requirements: {task.get('requirements', [])}
            - Difficulty Level: {task.get('difficulty_level', 'intermediate')}
            
            Intern Profile:
            - Experience Level: {intern_profile.get('experience_level', 'beginner')}
            - Skills: {intern_profile.get('skills', [])}
            - Previous Performance: {intern_profile.get('performance_score', 0)}
            
            Code Analysis Results:
            {json.dumps(file_analyses, indent=2)}
            
            Provide comprehensive evaluation in JSON format:
            1. overall_score: Score out of 100
            2. category_scores: Scores for code_quality, functionality, creativity, documentation
            3. strengths: List of strong points in the submission
            4. areas_for_improvement: Specific areas needing work
            5. detailed_feedback: Constructive feedback on each aspect
            6. code_review_comments: Specific line-by-line suggestions
            7. learning_recommendations: What the intern should focus on next
            8. grade_justification: Explanation of the scoring
            9. estimated_time_spent: Estimated time the intern spent on this task
            10. meets_requirements: Boolean indicating if requirements were met
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert code reviewer and technical mentor with extensive experience in evaluating student work."},
                    {"role": "user", "content": evaluation_prompt}
                ],
                temperature=0.2
            )
            
            evaluation_result = json.loads(response.choices[0].message.content)
            
            # Add metadata
            evaluation_result["evaluation_metadata"] = {
                "agent": self.name,
                "evaluation_date": datetime.utcnow().isoformat(),
                "files_analyzed": len(code_files),
                "total_lines_of_code": sum(len(f.get("content", "").split('\n')) for f in code_files),
                "evaluation_criteria_used": self.evaluation_criteria
            }
            
            # Generate improvement plan
            improvement_plan = await self._generate_improvement_plan(
                evaluation_result,
                intern_profile
            )
            evaluation_result["improvement_plan"] = improvement_plan
            
            self.log_activity("code_evaluated", {
                "overall_score": evaluation_result.get("overall_score"),
                "files_count": len(code_files),
                "meets_requirements": evaluation_result.get("meets_requirements")
            })
            
            return self.format_response(
                True,
                evaluation_result,
                "Code submission evaluated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Code evaluation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Code evaluation failed: {str(e)}"
            )
    
    async def evaluate_project_submission(self, submission_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate complete project submission"""
        try:
            project_info = submission_data.get("project_info", {})
            deliverables = submission_data.get("deliverables", [])
            documentation = submission_data.get("documentation", "")
            demo_video = submission_data.get("demo_video", "")
            intern_profile = submission_data.get("intern_profile", {})
            
            evaluation_prompt = f"""
            Evaluate this complete project submission:
            
            Project Information:
            - Title: {project_info.get('title', '')}
            - Description: {project_info.get('description', '')}
            - Technologies Used: {project_info.get('technologies', [])}
            - Duration: {project_info.get('duration_weeks', 0)} weeks
            - Complexity Level: {project_info.get('complexity', 'medium')}
            
            Deliverables Submitted:
            {json.dumps(deliverables, indent=2)}
            
            Documentation Quality:
            - Length: {len(documentation.split()) if documentation else 0} words
            - Has Demo Video: {'Yes' if demo_video else 'No'}
            
            Intern Profile:
            - Experience Level: {intern_profile.get('experience_level')}
            - Skills: {intern_profile.get('skills', [])}
            
            Evaluate across these dimensions in JSON format:
            1. overall_score: Score out of 100
            2. dimension_scores: Scores for technical_execution, project_scope, innovation, documentation, presentation
            3. project_highlights: Most impressive aspects
            4. technical_assessment: Technical quality and implementation
            5. scope_evaluation: How well the project meets its intended scope
            6. innovation_score: Creativity and unique problem-solving approaches
            7. professional_readiness: Assessment of industry-readiness
            8. detailed_feedback: Comprehensive feedback on all aspects
            9. recommendations: Suggestions for future projects
            10. portfolio_worthiness: Whether this project is portfolio-ready
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a senior technical project evaluator with industry experience in assessing student projects for professional readiness."},
                    {"role": "user", "content": evaluation_prompt}
                ],
                temperature=0.3
            )
            
            project_evaluation = json.loads(response.choices[0].message.content)
            
            # Add comprehensive project analysis
            project_evaluation["project_analysis"] = {
                "complexity_achieved": self._assess_project_complexity(project_info, deliverables),
                "technology_mastery": self._assess_technology_usage(project_info, deliverables),
                "best_practices_followed": self._identify_best_practices(deliverables),
                "areas_for_enhancement": self._identify_enhancement_opportunities(project_evaluation)
            }
            
            self.log_activity("project_evaluated", {
                "overall_score": project_evaluation.get("overall_score"),
                "deliverables_count": len(deliverables),
                "portfolio_worthy": project_evaluation.get("portfolio_worthiness")
            })
            
            return self.format_response(
                True,
                project_evaluation,
                "Project submission evaluated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Project evaluation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Project evaluation failed: {str(e)}"
            )
    
    async def evaluate_written_assignment(self, submission_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate written assignments, reports, and documentation"""
        try:
            assignment = submission_data.get("assignment_info", {})
            content = submission_data.get("content", "")
            intern_profile = submission_data.get("intern_profile", {})
            
            # Analyze content metrics
            word_count = len(content.split()) if content else 0
            paragraph_count = len([p for p in content.split('\n\n') if p.strip()]) if content else 0
            
            evaluation_prompt = f"""
            Evaluate this written assignment:
            
            Assignment Details:
            - Title: {assignment.get('title', '')}
            - Type: {assignment.get('type', 'report')}
            - Required Length: {assignment.get('required_words', 'Not specified')} words
            - Topic: {assignment.get('topic', '')}
            
            Submission Analysis:
            - Word Count: {word_count}
            - Paragraph Count: {paragraph_count}
            - Estimated Reading Time: {word_count // 200} minutes
            
            Content:
            {content[:2000]}...  # First 2000 characters
            
            Intern Level: {intern_profile.get('experience_level', 'beginner')}
            
            Evaluate in JSON format:
            1. overall_score: Score out of 100
            2. content_quality: Quality of ideas and arguments
            3. structure_organization: Logical flow and organization
            4. writing_clarity: Clarity and readability
            5. technical_accuracy: Technical correctness of content
            6. depth_of_analysis: Depth of thinking and analysis
            7. grammar_style: Grammar, style, and language usage
            8. strengths: What the intern did well
            9. improvements: Specific areas for improvement
            10. writing_level_assessment: Assessment of current writing level
            11. development_recommendations: How to improve writing skills
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert writing instructor and technical communication specialist."},
                    {"role": "user", "content": evaluation_prompt}
                ],
                temperature=0.2
            )
            
            writing_evaluation = json.loads(response.choices[0].message.content)
            
            # Add readability analysis
            writing_evaluation["readability_analysis"] = {
                "word_count": word_count,
                "paragraph_count": paragraph_count,
                "avg_words_per_paragraph": word_count / max(paragraph_count, 1),
                "estimated_reading_level": self._estimate_reading_level(content),
                "technical_term_usage": self._count_technical_terms(content)
            }
            
            self.log_activity("written_assignment_evaluated", {
                "overall_score": writing_evaluation.get("overall_score"),
                "word_count": word_count,
                "writing_level": writing_evaluation.get("writing_level_assessment")
            })
            
            return self.format_response(
                True,
                writing_evaluation,
                "Written assignment evaluated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Written assignment evaluation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Written assignment evaluation failed: {str(e)}"
            )
    
    async def _analyze_code_file(self, filename: str, content: str, language: str) -> Dict[str, Any]:
        """Analyze individual code file"""
        
        # Basic code metrics
        lines_of_code = len([line for line in content.split('\n') if line.strip() and not line.strip().startswith('#')])
        comment_lines = len([line for line in content.split('\n') if line.strip().startswith('#')])
        
        analysis_prompt = f"""
        Analyze this {language} code file:
        
        Filename: {filename}
        Language: {language}
        Lines of Code: {lines_of_code}
        Comment Lines: {comment_lines}
        
        Code Content:
        {content[:1500]}...
        
        Provide analysis in JSON format:
        1. code_quality_score: Score out of 10
        2. readability_score: How readable is the code (1-10)
        3. structure_score: How well structured (1-10)
        4. best_practices_score: Adherence to best practices (1-10)
        5. issues_found: List of issues or problems
        6. good_practices: List of good practices observed
        7. suggestions: Specific improvement suggestions
        8. complexity_level: Estimated complexity (low/medium/high)
        
        Return only valid JSON.
        """
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are an expert {language} code reviewer."},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.1
        )
        
        file_analysis = json.loads(response.choices[0].message.content)
        file_analysis["filename"] = filename
        file_analysis["metrics"] = {
            "lines_of_code": lines_of_code,
            "comment_lines": comment_lines,
            "comment_ratio": comment_lines / max(lines_of_code, 1)
        }
        
        return file_analysis
    
    async def _generate_improvement_plan(self, evaluation: Dict[str, Any], intern_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Generate personalized improvement plan based on evaluation"""
        
        plan_prompt = f"""
        Create a personalized improvement plan:
        
        Current Evaluation:
        - Overall Score: {evaluation.get('overall_score', 0)}
        - Strengths: {evaluation.get('strengths', [])}
        - Areas for Improvement: {evaluation.get('areas_for_improvement', [])}
        
        Intern Profile:
        - Experience Level: {intern_profile.get('experience_level', 'beginner')}
        - Current Skills: {intern_profile.get('skills', [])}
        
        Create improvement plan in JSON format:
        1. priority_areas: Top 3 areas to focus on
        2. learning_resources: Specific resources for each area
        3. practice_exercises: Recommended exercises
        4. timeline: Suggested timeline for improvements
        5. milestones: Key milestones to track progress
        6. next_project_suggestions: Ideas for next projects
        
        Return only valid JSON.
        """
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a learning and development specialist for technical skills."},
                {"role": "user", "content": plan_prompt}
            ],
            temperature=0.3
        )
        
        return json.loads(response.choices[0].message.content)
    
    def _assess_project_complexity(self, project_info: Dict[str, Any], deliverables: List[Dict]) -> str:
        """Assess achieved project complexity"""
        tech_count = len(project_info.get("technologies", []))
        deliverable_count = len(deliverables)
        duration = project_info.get("duration_weeks", 0)
        
        complexity_score = tech_count * 2 + deliverable_count + duration
        
        if complexity_score >= 15:
            return "high"
        elif complexity_score >= 8:
            return "medium"
        else:
            return "low"
    
    def _estimate_reading_level(self, content: str) -> str:
        """Estimate reading level of written content"""
        if not content:
            return "unknown"
        
        words = content.split()
        sentences = re.split(r'[.!?]+', content)
        
        avg_words_per_sentence = len(words) / max(len(sentences), 1)
        
        if avg_words_per_sentence > 20:
            return "advanced"
        elif avg_words_per_sentence > 15:
            return "intermediate"
        else:
            return "beginner"
