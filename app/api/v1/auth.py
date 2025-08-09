from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    generate_password_reset_token,
    verify_password_reset_token
)
from app.core.config import settings
from app.schemas.user import UserCreate, UserResponse, Token, PasswordReset
from app.services.auth_service import (
    create_user,
    get_user_by_email,
    get_user_by_username,
    update_user_password
)
from app.services.notification_service import send_password_reset_email
from app.api.deps import get_current_active_user
from app.models.user import User

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Register new user"""
    # Check if user already exists
    if get_user_by_email(db, email=user_data.email):
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    if get_user_by_username(db, username=user_data.username):
        raise HTTPException(
            status_code=400,
            detail="Username already taken"
        )
    
    # Create new user
    user = create_user(db=db, user=user_data)
    
    # Send welcome email
    background_tasks.add_task(
        send_welcome_email,
        user.email,
        user.first_name
    )
    
    return user

@router.post("/login", response_model=Token)
async def login(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """User login"""
    user = get_user_by_username(db, username=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    
    # Update last login
    update_last_login(db, user.id)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user profile"""
    return current_user

@router.post("/password-reset-request")
async def password_reset_request(
    email: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Request password reset"""
    user = get_user_by_email(db, email=email)
    if not user:
        # Don't reveal if email exists or not
        return {"message": "Password reset email sent if account exists"}
    
    reset_token = generate_password_reset_token(email=email)
    background_tasks.add_task(
        send_password_reset_email,
        email,
        reset_token
    )
    
    return {"message": "Password reset email sent if account exists"}

@router.post("/password-reset")
async def reset_password(
    reset_data: PasswordReset,
    db: Session = Depends(get_db)
):
    """Reset password with token"""
    email = verify_password_reset_token(reset_data.token)
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired token"
        )
    
    user = get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    update_user_password(db, user.id, reset_data.new_password)
    
    return {"message": "Password reset successful"}

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user)
):
    """User logout (client should discard token)"""
    return {"message": "Successfully logged out"}
