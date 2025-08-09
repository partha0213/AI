from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError, NotFoundError
from app.models.user import User
from app.schemas.user import UserCreate
from app.utils.email import send_welcome_email

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)

def create_user(db: Session, user: UserCreate) -> User:
    """Create new user"""
    # Hash password
    hashed_password = get_password_hash(user.password)
    
    # Create user instance
    db_user = User(
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        hashed_password=hashed_password,
        role=user.role,
        phone=user.phone,
        is_active=True,
        is_verified=False
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate user with username/email and password"""
    user = get_user_by_username_or_email(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username"""
    return db.query(User).filter(User.username == username).first()

def get_user_by_username_or_email(db: Session, identifier: str) -> Optional[User]:
    """Get user by username or email"""
    return db.query(User).filter(
        or_(User.username == identifier, User.email == identifier)
    ).first()

def update_user_password(db: Session, user_id: int, new_password: str) -> User:
    """Update user password"""
    user = get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")
    
    user.hashed_password = get_password_hash(new_password)
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user

def update_last_login(db: Session, user_id: int):
    """Update user's last login timestamp"""
    user = get_user_by_id(db, user_id)
    if user:
        user.last_login = datetime.utcnow()
        db.commit()

def verify_user_email(db: Session, user_id: int) -> User:
    """Mark user email as verified"""
    user = get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")
    
    user.is_verified = True
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user

def deactivate_user(db: Session, user_id: int) -> User:
    """Deactivate user account"""
    user = get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")
    
    user.is_active = False
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user

def activate_user(db: Session, user_id: int) -> User:
    """Activate user account"""
    user = get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")
    
    user.is_active = True
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user

def create_access_token(subject: int, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> str:
    """Verify JWT token and return user ID"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token")
        return user_id
    except JWTError:
        raise AuthenticationError("Invalid token")

def generate_password_reset_token(email: str) -> str:
    """Generate password reset token"""
    expire = datetime.utcnow() + timedelta(hours=1)
    to_encode = {"exp": expire, "sub": email, "type": "password_reset"}
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token

def verify_password_reset_token(token: str) -> str:
    """Verify password reset token and return email"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "password_reset":
            raise AuthenticationError("Invalid token")
        return email
    except JWTError:
        raise AuthenticationError("Invalid or expired token")

def check_user_permissions(user: User, required_role: str) -> bool:
    """Check if user has required role permissions"""
    role_hierarchy = {
        "intern": 1,
        "mentor": 2,
        "hr": 3,
        "admin": 4
    }
    
    user_level = role_hierarchy.get(user.role.value, 0)
    required_level = role_hierarchy.get(required_role, 0)
    
    return user_level >= required_level

def get_user_display_name(db: Session, user_id: int) -> str:
    """Get user's display name"""
    user = get_user_by_id(db, user_id)
    if not user:
        return "Unknown User"
    
    return f"{user.first_name} {user.last_name}".strip()
