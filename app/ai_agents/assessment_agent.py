import openai
import json
from typing import Dict, Any, List
import PyPDF2
import docx
from io import BytesIO

from app.ai_agents.base_agent import BaseAgent
from app.core.config import settings

openai.api_key = settings.OPENAI_API_KEY

class AssessmentAgent(BaseAgent):
    """AI agent for skills assessment and CV parsing"""
    
    def __init__(self):
        super().__init__("assessment_agent")
        self.skills_categories = [
            "Programming Languages",
            "Web Technologies",
            "Databases",
            "Cloud Platforms",
            "Machine Learning",
            "Data Analysis",
            "Project Management",
            "Communication",
            "Leadership"
        ]
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process assessment request"""
        assessment_type = data.get("type")
        
        if assessment_type == "resume_analysis":
            return await self.analyze_resume(data.get("file_content"))
        elif assessment_type == "skill_assessment":
            return await self.assess_skills(data.get("intern_data"))
        elif assessment_type == "quiz_evaluation":
            return await self.evaluate_quiz(data.get("quiz_responses"))
        else:
            return self.format_response(
                False, 
                None, 
                "Invalid assessment type"
            )
    
    async def analyze_resume(self, file_content: bytes) -> Dict[str, Any]:
        """Analyze resume/CV content"""
        try:
            # Extract text from file
            text_content = await self._extract_text_from_file(file_content)
            
            # Use OpenAI to analyze resume
            analysis_prompt = f"""
            Analyze this resume/CV and extract the following information in JSON format:
            
            Resume Content:
            {text_content}
            
            Please provide:
            1. skills: List of technical and soft skills
            2. experience_level: "Beginner", "Intermediate", or "Advanced"
            3. education: Education details
            4. experience_summary: Brief summary of work experience
            5. projects: List of notable projects
            6. certifications: Any certifications mentioned
            7. programming_languages: List of programming languages
            8. overall_score: Score out of 100 based on completeness and quality
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert resume analyzer. Return only valid JSON."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3
            )
            
            analysis_result = json.loads(response.choices[0].message.content)
            
            self.log_activity("resume_analyzed", {
                "skills_found": len(analysis_result.get("skills", [])),
                "experience_level": analysis_result.get("experience_level")
            })
            
            return self.format_response(
                True,
                analysis_result,
                "Resume analyzed successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Resume analysis failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Resume analysis failed: {str(e)}"
            )
    
    async def assess_skills(self, intern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive skill assessment"""
        try:
            assessment_prompt = f"""
            Based on the following intern information, provide a comprehensive skill assessment:
            
            Intern Data:
            - Skills: {intern_data.get('skills', [])}
            - Education: {intern_data.get('education', {})}
            - Experience: {intern_data.get('experience', '')}
            - Projects: {intern_data.get('projects', [])}
            
            Provide assessment in JSON format:
            1. skill_breakdown: Object with skill categories and scores (0-100)
            2. overall_score: Overall skill score (0-100)
            3. strengths: List of key strengths
            4. improvement_areas: List of areas needing improvement
            5. recommended_track: Suggested internship track
            6. personality_traits: Inferred personality traits
            7. learning_style: Suggested learning approach
            8. difficulty_level: Recommended task difficulty ("Beginner", "Intermediate", "Advanced")
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert skills assessor for internship programs."},
                    {"role": "user", "content": assessment_prompt}
                ],
                temperature=0.2
            )
            
            assessment_result = json.loads(response.choices[0].message.content)
            
            self.log_activity("skills_assessed", {
                "overall_score": assessment_result.get("overall_score"),
                "recommended_track": assessment_result.get("recommended_track")
            })
            
            return self.format_response(
                True,
                assessment_result,
                "Skills assessed successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Skills assessment failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Skills assessment failed: {str(e)}"
            )
    
    async def evaluate_quiz(self, quiz_responses: List[Dict]) -> Dict[str, Any]:
        """Evaluate quiz responses"""
        try:
            total_questions = len(quiz_responses)
            correct_answers = 0
            category_scores = {}
            
            for response in quiz_responses:
                if response.get("is_correct"):
                    correct_answers += 1
                
                category = response.get("category", "General")
                if category not in category_scores:
                    category_scores[category] = {"correct": 0, "total": 0}
                
                category_scores[category]["total"] += 1
                if response.get("is_correct"):
                    category_scores[category]["correct"] += 1
            
            # Calculate percentage scores
            overall_score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
            
            for category in category_scores:
                correct = category_scores[category]["correct"]
                total = category_scores[category]["total"]
                category_scores[category]["percentage"] = (correct / total) * 100 if total > 0 else 0
            
            result = {
                "overall_score": round(overall_score, 2),
                "correct_answers": correct_answers,
                "total_questions": total_questions,
                "category_scores": category_scores,
                "performance_level": self._get_performance_level(overall_score)
            }
            
            self.log_activity("quiz_evaluated", {
                "score": overall_score,
                "total_questions": total_questions
            })
            
            return self.format_response(
                True,
                result,
                "Quiz evaluated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Quiz evaluation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Quiz evaluation failed: {str(e)}"
            )
    
    async def _extract_text_from_file(self, file_content: bytes) -> str:
        """Extract text from PDF or DOCX file"""
        # This is a simplified implementation
        # In production, you'd want more robust file processing
        try:
            # Try to decode as text first
            return file_content.decode('utf-8')
        except UnicodeDecodeError:
            # If it fails, assume it's a binary format
            return "Binary file content - implement proper PDF/DOCX parsing"
    
    def _get_performance_level(self, score: float) -> str:
        """Determine performance level based on score"""
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Very Good"
        elif score >= 70:
            return "Good"
        elif score >= 60:
            return "Average"
        else:
            return "Needs Improvement"
