import re
import validators
from typing import List, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel, validator
from app.core.exceptions import ValidationError

class EmailValidator:
    """Email validation utilities"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email format"""
        return validators.email(email)
    
    @staticmethod
    def is_business_email(email: str) -> bool:
        """Check if email is from a business domain"""
        free_domains = [
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'aol.com', 'icloud.com', 'protonmail.com'
        ]
        domain = email.split('@')[1].lower() if '@' in email else ''
        return domain not in free_domains
    
    @staticmethod
    def normalize_email(email: str) -> str:
        """Normalize email address"""
        return email.strip().lower()

class PasswordValidator:
    """Password validation utilities"""
    
    @staticmethod
    def validate_strength(password: str) -> dict:
        """Validate password strength"""
        
        result = {
            'valid': True,
            'score': 0,
            'requirements': {
                'length': len(password) >= 8,
                'uppercase': bool(re.search(r'[A-Z]', password)),
                'lowercase': bool(re.search(r'[a-z]', password)),
                'numbers': bool(re.search(r'\d', password)),
                'special_chars': bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
            },
            'suggestions': []
        }
        
        # Calculate score
        for requirement, met in result['requirements'].items():
            if met:
                result['score'] += 20
        
        # Add suggestions
        if not result['requirements']['length']:
            result['suggestions'].append('Use at least 8 characters')
        if not result['requirements']['uppercase']:
            result['suggestions'].append('Include uppercase letters')
        if not result['requirements']['lowercase']:
            result['suggestions'].append('Include lowercase letters')
        if not result['requirements']['numbers']:
            result['suggestions'].append('Include numbers')
        if not result['requirements']['special_chars']:
            result['suggestions'].append('Include special characters')
        
        # Check if valid
        result['valid'] = all(result['requirements'].values())
        
        return result
    
    @staticmethod
    def is_common_password(password: str) -> bool:
        """Check if password is commonly used"""
        common_passwords = [
            'password', '123456', '12345678', 'qwerty', 'abc123',
            'password123', 'admin', 'letmein', 'welcome', 'monkey'
        ]
        return password.lower() in common_passwords

class PhoneValidator:
    """Phone number validation utilities"""
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format"""
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
