import secrets
import hashlib
import re
from typing import List, Dict, Any
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

class SecurityConfig:
    """Production security configuration"""
    
    # Generate secure random keys
    SECRET_KEY = secrets.token_urlsafe(32)
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    
    # Security settings
    ALLOWED_ORIGINS = [
        "https://yourdomain.com",
        "https://www.yourdomain.com",
        "https://admin.yourdomain.com"
    ]
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE = 60
    RATE_LIMIT_BURST = 100
    
    # File upload security
    MAX_FILE_SIZE_MB = 50
    ALLOWED_FILE_TYPES = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']
    
    # AI-specific security
    MAX_PROMPT_LENGTH = 4000
    BLOCKED_PATTERNS = [
        "ignore previous instructions",
        "act as",
        "pretend to be",
        "system:",
        "assistant:",
        "jailbreak",
        "dev mode"
    ]

class AISecurityValidator:
    """Validates AI inputs for security threats"""
    
    @staticmethod
    def validate_prompt(prompt: str) -> bool:
        """Check prompt for injection attempts"""
        prompt_lower = prompt.lower()
        
        for pattern in SecurityConfig.BLOCKED_PATTERNS:
            if pattern in prompt_lower:
                logger.warning(f"Blocked prompt injection attempt: {pattern}")
                return False
        
        return True
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input"""
        # Remove potential script injections
        text = re.sub(r'<script.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove dangerous patterns
        for pattern in SecurityConfig.BLOCKED_PATTERNS:
            text = re.sub(pattern, '[REDACTED]', text, flags=re.IGNORECASE)
        
        # Limit length
        if len(text) > SecurityConfig.MAX_PROMPT_LENGTH:
            text = text[:SecurityConfig.MAX_PROMPT_LENGTH] + "...[truncated]"
        
        return text

class AdvancedRateLimiter:
    """Advanced rate limiting with different tiers"""
    
    def __init__(self):
        self.rate_limits = {
            'standard': {'requests': 100, 'window': 3600},  # 100/hour
            'premium': {'requests': 500, 'window': 3600},   # 500/hour
            'ai_heavy': {'requests': 50, 'window': 3600}    # 50/hour for AI endpoints
        }
        self.client_requests = {}
    
    def is_allowed(self, client_id: str, tier: str = 'standard') -> bool:
        """Check if request is within rate limit"""
        import time
        
        now = time.time()
        window = self.rate_limits[tier]['window']
        limit = self.rate_limits[tier]['requests']
        
        if client_id not in self.client_requests:
            self.client_requests[client_id] = []
        
        # Clean old requests
        self.client_requests[client_id] = [
            req_time for req_time in self.client_requests[client_id]
            if now - req_time < window
        ]
        
        # Check limit
        if len(self.client_requests[client_id]) >= limit:
            return False
        
        # Record request
        self.client_requests[client_id].append(now)
        return True

# Global instances
security_validator = AISecurityValidator()
rate_limiter = AdvancedRateLimiter()
