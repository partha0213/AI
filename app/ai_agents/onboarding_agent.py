import openai
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid

from app.ai_agents.base_agent import BaseAgent
from app.core.config import settings
from app.services.email import send_welcome_email
from app.services.notification_service import notification_service

openai.api_key = settings.OPENAI_API_KEY

class OnboardingAgent(BaseAgent):
    """AI agent for automating intern onboarding processes"""
    
    def __init__(self):
        super().__init__("onboarding_agent")
        self.onboarding_templates = {
            "web_development": {
                "welcome_message": "Welcome to our Web Development internship program!",
                "initial_resources": [
                    "HTML/CSS Fundamentals",
                    "JavaScript Basics", 
                    "Git & Version Control",
                    "Development Environment Setup"
                ],
                "first_week_goals": [
                    "Set up development environment",
                    "Complete HTML/CSS tutorial",
                    "Create your first web page",
                    "Learn Git basics"
                ]
            },
            "data_science": {
                "welcome_message": "Welcome to our Data Science internship program!",
                "initial_resources": [
                    "Python Fundamentals",
                    "Data Analysis with Pandas",
                    "Statistics Basics",
                    "Jupyter Notebook Setup"
                ],
                "first_week_goals": [
                    "Set up Python environment",
                    "Complete Python basics",
                    "Learn Pandas fundamentals",
                    "Analyze your first dataset"
                ]
            },
            "mobile_development": {
                "welcome_message": "Welcome to our Mobile Development internship program!",
                "initial_resources": [
                    "Mobile Development Fundamentals",
                    "React Native Basics",
                    "Mobile UI/UX Principles",
                    "Development Tools Setup"
                ],
                "first_week_goals": [
                    "Set up development environment",
                    "Create your first mobile app",
                    "Learn React Native components",
                    "Understand mobile design patterns"
                ]
            }
        }
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process onboarding requests"""
        operation = data.get("type")
        
        if operation == "create_profile":
            return await self.create_comprehensive_profile(data.get("intern_data"))
        elif operation == "generate_welcome_package":
            return await self.generate_welcome_package(data.get("intern_data"))
        elif operation == "setup_learning_environment":
            return await self.setup_learning_environment(data.get("intern_data"))
        elif operation == "create_onboarding_schedule":
            return await self.create_onboarding_schedule(data.get("intern_data"))
        elif operation == "generate_mentor_introduction":
            return await self.generate_mentor_introduction(data.get("intern_data"), data.get("mentor_data"))
        else:
            return self.format_response(
                False,
                None,
                "Invalid onboarding operation"
            )
    
    async def create_comprehensive_profile(self, intern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive intern profile with AI enhancement"""
        try:
            profile_prompt = f"""
            Create a comprehensive intern profile based on the provided information:
            
            Basic Information:
            - Name: {intern_data.get('name', '')}
            - Email: {intern_data.get('email', '')}
            - University: {intern_data.get('university', '')}
            - Major: {intern_data.get('major', '')}
            - Graduation Year: {intern_data.get('graduation_year', '')}
            - Program Track: {intern_data.get('program_track', '')}
            
            Skills and Experience:
            - Listed Skills: {intern_data.get('skills', [])}
            - Experience Level: {intern_data.get('experience_level', 'beginner')}
            - Previous Projects: {intern_data.get('projects', [])}
            - GitHub: {intern_data.get('github_url', '')}
            - LinkedIn: {intern_data.get('linkedin_url', '')}
            
            Generate enhanced profile in JSON format:
            1. intern_id: Generate unique intern ID (format: INT-YYYY-XXXX)
            2. profile_summary: Professional summary paragraph
            3. skill_assessment: Categorized skills with proficiency levels
            4. learning_goals: Suggested learning objectives based on track
            5. expected_outcomes: What intern should achieve by end of program
            6. personality_traits: Inferred traits based on information provided
            7. communication_preferences: Suggested communication style
            8. potential_challenges: Areas that might need extra support
            9. strengths_to_leverage: Key strengths to build upon
            10. recommended_track_alignment: How well they fit their chosen track
            
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert HR specialist and intern program coordinator with extensive experience in creating comprehensive profiles."},
                    {"role": "user", "content": profile_prompt}
                ],
                temperature=0.3
            )
            
            enhanced_profile = json.loads(response.choices[0].message.content)
            
            # Generate unique intern ID if not provided by AI
            if not enhanced_profile.get("intern_id"):
                year = datetime.now().year
                unique_id = str(uuid.uuid4())[:4].upper()
                enhanced_profile["intern_id"] = f"INT-{year}-{unique_id}"
            
            # Add creation metadata
            enhanced_profile["profile_created_at"] = datetime.utcnow().isoformat()
            enhanced_profile["created_by_agent"] = self.name
            enhanced_profile["original_data"] = intern_data
            
            self.log_activity("profile_created", {
                "intern_id": enhanced_profile["intern_id"],
                "program_track": intern_data.get('program_track'),
                "experience_level": intern_data.get('experience_level')
            })
            
            return self.format_response(
                True,
                enhanced_profile,
                "Comprehensive intern profile created successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Profile creation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Profile creation failed: {str(e)}"
            )
    
    async def generate_welcome_package(self, intern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate personalized welcome package"""
        try:
            program_track = intern_data.get('program_track', 'general').lower().replace(' ', '_')
            template = self.onboarding_templates.get(program_track, self.onboarding_templates['web_development'])
            
            welcome_prompt = f"""
            Create a personalized welcome package for this intern:
            
            Intern Information:
            - Name: {intern_data.get('name', '')}
            - Program Track: {intern_data.get('program_track', '')}
            - Experience Level: {intern_data.get('experience_level', 'beginner')}
            - University: {intern_data.get('university', '')}
            - Skills: {intern_data.get('skills', [])}
            
            Generate welcome package in JSON format:
            1. personalized_welcome_message: Warm, encouraging welcome message
            2. program_overview: Overview of what to expect in the program
            3. first_day_agenda: Detailed agenda for the first day
            4. first_week_checklist: Action items for the first week
            5. key_contacts: Important people they should know
            6. essential_resources: Must-have resources and tools
            7. success_tips: Tips for succeeding in the internship
            8. common_questions: FAQ relevant to their track
            9. milestone_timeline: Key milestones for the first month
            10. support_channels: How to get help when needed
            
            Make it encouraging, informative, and specific to their background.
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a welcoming and knowledgeable internship coordinator who creates engaging onboarding materials."},
                    {"role": "user", "content": welcome_prompt}
                ],
                temperature=0.4
            )
            
            welcome_package = json.loads(response.choices[0].message.content)
            
            # Add template-based resources
            welcome_package["template_resources"] = template["initial_resources"]
            welcome_package["template_goals"] = template["first_week_goals"]
            
            # Add practical information
            welcome_package["practical_info"] = {
                "start_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                "program_duration": "12 weeks",
                "working_hours": "9:00 AM - 5:00 PM",
                "time_zone": "EST",
                "dress_code": "Business casual (remote-friendly)"
            }
            
            # Generate welcome checklist
            welcome_package["pre_start_checklist"] = await self._generate_pre_start_checklist(intern_data)
            
            self.log_activity("welcome_package_generated", {
                "intern_name": intern_data.get('name'),
                "program_track": program_track,
                "resources_count": len(welcome_package.get("essential_resources", []))
            })
            
            return self.format_response(
                True,
                welcome_package,
                "Personalized welcome package generated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Welcome package generation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Welcome package generation failed: {str(e)}"
            )
    
    async def setup_learning_environment(self, intern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set up personalized learning environment"""
        try:
            program_track = intern_data.get('program_track', '').lower()
            experience_level = intern_data.get('experience_level', 'beginner')
            
            setup_prompt = f"""
            Create a learning environment setup guide for this intern:
            
            Intern Profile:
            - Program Track: {intern_data.get('program_track', '')}
            - Experience Level: {experience_level}
            - Skills: {intern_data.get('skills', [])}
            - Operating System: {intern_data.get('os_preference', 'Not specified')}
            
            Generate setup guide in JSON format:
            1. development_tools: Required tools and software
            2. installation_guide: Step-by-step installation instructions
            3. configuration_steps: Configuration and setup steps
            4. verification_checklist: How to verify everything is working
            5. troubleshooting_tips: Common issues and solutions
            6. learning_platforms: Recommended learning platforms and accounts
            7. project_structure: Recommended folder structure for projects
            8. best_practices: Development best practices for beginners
            9. shortcuts_and_tips: Productivity tips and keyboard shortcuts
            10. additional_resources: Links to documentation and tutorials
            
            Tailor recommendations to their experience level and track.
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a technical setup specialist who helps new developers get their environment ready efficiently."},
                    {"role": "user", "content": setup_prompt}
                ],
                temperature=0.2
            )
            
            setup_guide = json.loads(response.choices[0].message.content)
            
            # Add track-specific tools
            if 'web' in program_track:
                setup_guide["track_specific_tools"] = [
                    "Visual Studio Code",
                    "Node.js",
                    "Git",
                    "Browser Developer Tools",
                    "Postman"
                ]
            elif 'data' in program_track:
                setup_guide["track_specific_tools"] = [
                    "Python",
                    "Jupyter Notebook",
                    "Pandas",
                    "NumPy",
                    "Git"
                ]
            elif 'mobile' in program_track:
                setup_guide["track_specific_tools"] = [
                    "React Native CLI",
                    "Android Studio",
                    "Xcode (Mac only)",
                    "Node.js",
                    "Git"
                ]
            
            # Add environment validation script
            setup_guide["validation_script"] = self._generate_validation_script(program_track)
            
            self.log_activity("learning_environment_setup", {
                "program_track": program_track,
                "experience_level": experience_level,
                "tools_count": len(setup_guide.get("development_tools", []))
            })
            
            return self.format_response(
                True,
                setup_guide,
                "Learning environment setup guide generated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Learning environment setup failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Learning environment setup failed: {str(e)}"
            )
    
    async def create_onboarding_schedule(self, intern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create detailed onboarding schedule"""
        try:
            schedule_prompt = f"""
            Create a comprehensive 2-week onboarding schedule for this intern:
            
            Intern Details:
            - Name: {intern_data.get('name', '')}
            - Program Track: {intern_data.get('program_track', '')}
            - Experience Level: {intern_data.get('experience_level', 'beginner')}
            - Start Date: {intern_data.get('start_date', 'Next Monday')}
            
            Generate schedule in JSON format:
            1. week_1: Detailed day-by-day schedule for first week
            2. week_2: Detailed day-by-day schedule for second week
            3. daily_structure: Typical daily structure template
            4. meetings_schedule: All scheduled meetings and check-ins
            5. milestones: Key milestones and deliverables
            6. assessment_points: When assessments will occur
            7. flexibility_options: Options for adjusting pace
            8. support_touchpoints: When and how support will be provided
            
            Each day should include:
            - Morning objectives
            - Learning activities
            - Practical exercises
            - Meetings/check-ins
            - Evening wrap-up
            
            Balance learning, practice, and human interaction.
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert onboarding specialist who creates structured yet flexible learning schedules."},
                    {"role": "user", "content": schedule_prompt}
                ],
                temperature=0.3
            )
            
            schedule = json.loads(response.choices[0].message.content)
            
            # Add calendar integration information
            schedule["calendar_integration"] = {
                "ics_file_available": True,
                "outlook_compatible": True,
                "google_calendar_link": "Generated upon request",
                "timezone": "EST"
            }
            
            # Add buffer time recommendations
            schedule["scheduling_tips"] = [
                "Build in 15-minute buffers between activities",
                "Schedule challenging tasks for your peak energy hours",
                "Include regular breaks every 90 minutes",
                "End each day with a reflection exercise"
            ]
            
            self.log_activity("onboarding_schedule_created", {
                "intern_name": intern_data.get('name'),
                "total_days": 10,
                "program_track": intern_data.get('program_track')
            })
            
            return self.format_response(
                True,
                schedule,
                "Comprehensive onboarding schedule created successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Onboarding schedule creation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Onboarding schedule creation failed: {str(e)}"
            )
    
    async def generate_mentor_introduction(self, intern_data: Dict[str, Any], mentor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate introduction between intern and mentor"""
        try:
            intro_prompt = f"""
            Create a mentor-intern introduction package:
            
            Intern Information:
            - Name: {intern_data.get('name', '')}
            - Program Track: {intern_data.get('program_track', '')}
            - Experience Level: {intern_data.get('experience_level', '')}
            - Background: {intern_data.get('university', '')}, {intern_data.get('major', '')}
            - Interests: {intern_data.get('interests', [])}
            
            Mentor Information:
            - Name: {mentor_data.get('name', '')}
            - Role: {mentor_data.get('designation', '')}
            - Department: {mentor_data.get('department', '')}
            - Experience: {mentor_data.get('years_of_experience', '')} years
            - Expertise: {mentor_data.get('expertise_areas', [])}
            
            Generate introduction package in JSON format:
            1. introduction_email_intern: Email to intern about their mentor
            2. introduction_email_mentor: Email to mentor about their intern
            3. meeting_agenda: Agenda for their first meeting
            4. conversation_starters: Ice-breaker questions and topics
            5. expectation_setting: Clear expectations for both parties
            6. communication_guidelines: How they should communicate
            7. goal_setting_framework: Framework for setting shared goals
            8. success_metrics: How to measure mentorship success
            9. escalation_process: What to do if issues arise
            10. resources_sharing: Relevant resources for both parties
            
            Make it warm, professional, and encouraging.
            Return only valid JSON.
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a mentorship coordinator who excels at creating meaningful connections between mentors and interns."},
                    {"role": "user", "content": intro_prompt}
                ],
                temperature=0.4
            )
            
            introduction_package = json.loads(response.choices[0].message.content)
            
            # Add structured meeting templates
            introduction_package["meeting_templates"] = {
                "first_meeting": {
                    "duration": "60 minutes",
                    "agenda": [
                        "Personal introductions (15 min)",
                        "Background and expectations (20 min)", 
                        "Goal setting (15 min)",
                        "Communication preferences (10 min)"
                    ]
                },
                "weekly_checkin": {
                    "duration": "30 minutes",
                    "agenda": [
                        "Progress review (10 min)",
                        "Challenges discussion (10 min)",
                        "Next week planning (10 min)"
                    ]
                }
            }
            
            # Add compatibility assessment
            introduction_package["compatibility_notes"] = await self._assess_mentor_intern_compatibility(
                intern_data, mentor_data
            )
            
            self.log_activity("mentor_introduction_generated", {
                "intern_name": intern_data.get('name'),
                "mentor_name": mentor_data.get('name'),
                "program_track": intern_data.get('program_track')
            })
            
            return self.format_response(
                True,
                introduction_package,
                "Mentor-intern introduction package generated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Mentor introduction generation failed: {str(e)}")
            return self.format_response(
                False,
                None,
                f"Mentor introduction generation failed: {str(e)}"
            )
    
    async def _generate_pre_start_checklist(self, intern_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate pre-start checklist based on intern data"""
        
        base_checklist = [
            {
                "task": "Complete profile setup",
                "description": "Fill out all required profile information",
                "priority": "high",
                "estimated_time": "15 minutes"
            },
            {
                "task": "Read welcome materials",
                "description": "Review all provided welcome documentation",
                "priority": "high", 
                "estimated_time": "30 minutes"
            },
            {
                "task": "Set up development environment",
                "description": "Install required tools and software",
                "priority": "high",
                "estimated_time": "2-3 hours"
            },
            {
                "task": "Join communication channels",
                "description": "Join Slack/Teams and introduce yourself",
                "priority": "medium",
                "estimated_time": "10 minutes"
            }
        ]
        
        # Add track-specific items
        program_track = intern_data.get('program_track', '').lower()
        if 'web' in program_track:
            base_checklist.extend([
                {
                    "task": "Set up Git and GitHub",
                    "description": "Create GitHub account and configure Git",
                    "priority": "high",
                    "estimated_time": "30 minutes"
                },
                {
                    "task": "Install browser dev tools",
                    "description": "Familiarize with Chrome/Firefox developer tools",
                    "priority": "medium", 
                    "estimated_time": "20 minutes"
                }
            ])
        elif 'data' in program_track:
            base_checklist.extend([
                {
                    "task": "Set up Python environment",
                    "description": "Install Python, Jupyter, and essential packages",
                    "priority": "high",
                    "estimated_time": "1 hour"
                },
                {
                    "task": "Download sample datasets",
                    "description": "Get familiar with data formats you'll work with",
                    "priority": "medium",
                    "estimated_time": "15 minutes"
                }
            ])
        
        return base_checklist
    
    def _generate_validation_script(self, program_track: str) -> str:
        """Generate environment validation script"""
        
        if 'web' in program_track.lower():
            return """
# Web Development Environment Validation
echo "Validating Web Development Environment..."

# Check Node.js
node --version && echo "✅ Node.js installed" || echo "❌ Node.js not found"

# Check npm
npm --version && echo "✅ npm installed" || echo "❌ npm not found"

# Check Git
git --version && echo "✅ Git installed" || echo "❌ Git not found"

# Check VS Code (optional)
code --version && echo "✅ VS Code installed" || echo "⚠️ VS Code not found (optional)"

echo "Environment validation complete!"
"""
        elif 'data' in program_track.lower():
            return """
# Data Science Environment Validation
echo "Validating Data Science Environment..."

# Check Python
python --version && echo "✅ Python installed" || echo "❌ Python not found"

# Check pip
pip --version && echo "✅ pip installed" || echo "❌ pip not found"

# Check Jupyter
jupyter --version && echo "✅ Jupyter installed" || echo "❌ Jupyter not found"

# Check essential packages
python -c "import pandas, numpy, matplotlib" && echo "✅ Essential packages installed" || echo "❌ Missing essential packages"

echo "Environment validation complete!"
"""
        else:
            return """
# General Environment Validation
echo "Validating Development Environment..."

# Check Git
git --version && echo "✅ Git installed" || echo "❌ Git not found"

# Check text editor availability
echo "✅ Environment validation complete!"
"""
    
    async def _assess_mentor_intern_compatibility(self, intern_data: Dict[str, Any], mentor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess compatibility between mentor and intern"""
        
        compatibility = {
            "track_alignment": "high" if intern_data.get('program_track') in mentor_data.get('expertise_areas', []) else "medium",
            "experience_gap": "appropriate",
            "communication_style": "compatible",
            "potential_synergies": [],
            "areas_to_watch": []
        }
        
        # Analyze experience gap
        intern_level = intern_data.get('experience_level', 'beginner')
        mentor_experience = mentor_data.get('years_of_experience', 0)
        
        if mentor_experience >= 5 and intern_level == 'beginner':
            compatibility["experience_gap"] = "excellent"
            compatibility["potential_synergies"].append("Mentor has deep experience to share")
        elif mentor_experience < 3 and intern_level == 'advanced':
            compatibility["experience_gap"] = "challenging"
            compatibility["areas_to_watch"].append("Ensure mentor can provide advanced guidance")
        
        return compatibility
