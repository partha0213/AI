from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, validator
from enum import Enum

from app.utils.validators import (
    validate_email_field,
    validate_password_field,
    validate_phone_field
)

class UserRole(str, Enum):
    INTERN = "intern"
    MENTOR = "mentor"
    ADMIN = "admin"
    HR = "hr"

class UserBase(BaseModel):
    email: EmailStr
    username: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: UserRole = UserRole.INTERN
    
    @validator('email')
    def validate_email(cls, v):
        return validate_email_field(v)
    
    @validator('phone')
    def validate_phone(cls, v):
        if v:
            return validate_phone_field(v)
        return v
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if not v.isalnum():
            raise ValueError('Username must contain only letters and numbers')
        return v.lower()

class UserCreate(UserBase):
    password: str
    confirm_password: str
    
    @validator('password')
    def validate_password(cls, v):
        return validate_password_field(v)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    profile_image: Optional[str] = None
    
    @validator('email')
    def validate_email(cls, v):
        if v:
            return validate_email_field(v)
        return v
    
    @validator('phone')
    def validate_phone(cls, v):
        if v:
            return validate_phone_field(v)
        return v

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    profile_image: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class PasswordReset(BaseModel):
    token: str
    new_password: str
    confirm_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        return validate_password_field(v)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class UserProfile(BaseModel):
    """Complete user profile with role-specific data"""
    user: UserResponse
    intern_profile: Optional[dict] = None
    mentor_profile: Optional[dict] = None
    
    class Config:
        from_attributes = True
