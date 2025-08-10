import secrets
import hashlib
import re
import time
from typing import List, Dict, Any
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, status
from collections import defaultdict
import logging

logger = logging.getLogger("security")

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
        "act as", "pretend to be",
        "system:", "assistant:",
        "jailbreak", "dev mode",
        "sudo", "admin",
        "bypass", "override",
        "execute", "eval",
        "<script", "</script>",
        "javascript:", "vbscript:"
    ]

class AISecurityValidator:
    """Validates AI inputs for security threats"""
    
    @staticmethod
    def validate_prompt(prompt: str) -> bool:
        """Check prompt for injection attempts"""
        if not prompt or len(prompt) > SecurityConfig.MAX_PROMPT_LENGTH:
            return False
            
        prompt_lower = prompt.lower()
        
        for pattern in SecurityConfig.BLOCKED_PATTERNS:
            if pattern in prompt_lower:
                logger.warning(f"Blocked prompt injection attempt: {pattern}")
                return False
        
        # Check for repeated characters (potential DoS)
        for char in prompt:
            if prompt.count(char) > 100:
                logger.warning("Blocked potential DoS attempt with repeated characters")
                return False
        
        return True
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input"""
        if not text:
            return ""
            
        # Remove potential script injections
        text = re.sub(r'<script.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        text = re.sub(r'vbscript:', '', text, flags=re.IGNORECASE)
        
        # Remove dangerous patterns
        for pattern in SecurityConfig.BLOCKED_PATTERNS:
            text = re.sub(re.escape(pattern), '[REDACTED]', text, flags=re.IGNORECASE)
        
        # Limit length
        if len(text) > SecurityConfig.MAX_PROMPT_LENGTH:
            text = text[:SecurityConfig.MAX_PROMPT_LENGTH] + "...[truncated]"
        
        return text
    
    @staticmethod
    def validate_file_content(content: bytes, filename: str) -> Dict[str, Any]:
        """Validate uploaded file content"""
        validation_result = {
            "is_safe": True,
            "warnings": [],
            "errors": []
        }
        
        # Check file size
        if len(content) > SecurityConfig.MAX_FILE_SIZE_MB * 1024 * 1024:
            validation_result["errors"].append("File too large")
            validation_result["is_safe"] = False
        
        # Check for malicious patterns in content
        content_lower = content.lower()
        malicious_patterns = [
            b'<script', b'javascript:', b'vbscript:',
            b'\x4d\x5a',  # PE executable header
            b'\x7f\x45\x4c\x46',  # ELF executable header
        ]
        
        for pattern in malicious_patterns:
            if pattern in content_lower:
                validation_result["errors"].append("Potentially malicious content detected")
                validation_result["is_safe"] = False
        
        return validation_result

class AdvancedRateLimiter:
    """Advanced rate limiting with different tiers"""
    
    def __init__(self):
        self.rate_limits = {
            'standard': {'requests': 100, 'window': 3600},  # 100/hour
            'premium': {'requests': 500, 'window': 3600},   # 500/hour
            'ai_heavy': {'requests': 50, 'window': 3600}    # 50/hour for AI endpoints
        }
        self.client_requests = defaultdict(list)
        self.blocked_ips = defaultdict(int)
    
    def is_allowed(self, client_id: str, tier: str = 'standard') -> bool:
        """Check if request is within rate limit"""
        now = time.time()
        
        # Check if IP is temporarily blocked
        if self.blocked_ips[client_id] > 0:
            if now - self.blocked_ips[client_id] < 3600:  # 1 hour block
                return False
            else:
                del self.blocked_ips[client_id]
        
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
            # Block IP if too many violations
            violations = sum(1 for req_time in self.client_requests[client_id] if now - req_time < 60)
            if violations > limit * 0.8:  # 80% of limit in 1 minute
                self.blocked_ips[client_id] = now
                logger.warning(f"IP blocked for rate limit violations: {client_id}")
            return False
        
        # Record request
        self.client_requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str, tier: str = 'standard') -> int:
        """Get remaining requests for client"""
        now = time.time()
        window = self.rate_limits[tier]['window']
        limit = self.rate_limits[tier]['requests']
        
        if client_id not in self.client_requests:
            return limit
        
        # Clean old requests
        self.client_requests[client_id] = [
            req_time for req_time in self.client_requests[client_id]
            if now - req_time < window
        ]
        
        return max(0, limit - len(self.client_requests[client_id]))

# Global instances
security_validator = AISecurityValidator()
rate_limiter = AdvancedRateLimiter()
