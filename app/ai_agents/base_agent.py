from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from app.core.config import settings

class BaseAgent(ABC):
    """Base class for all AI agents"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"ai_agent.{name}")
        self.created_at = datetime.utcnow()
    
    @abstractmethod
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data and return results"""
        pass
    
    def log_activity(self, action: str, details: Optional[Dict] = None):
        """Log agent activity"""
        log_data = {
            "agent": self.name,
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        self.logger.info(f"Agent activity: {log_data}")
    
    async def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data"""
        return isinstance(data, dict)
    
    def format_response(self, success: bool, data: Any, message: str = "") -> Dict[str, Any]:
        """Format standardized response"""
        return {
            "success": success,
            "data": data,
            "message": message,
            "agent": self.name,
            "timestamp": datetime.utcnow().isoformat()
        }
