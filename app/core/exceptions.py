from typing import Any, Dict, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)

class BaseAPIException(Exception):
    """Base exception class for API-specific errors"""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class AuthenticationError(BaseAPIException):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED, details)

class AuthorizationError(BaseAPIException):
    """Raised when user lacks required permissions"""
    
    def __init__(self, message: str = "Access denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_403_FORBIDDEN, details)

class NotFoundError(BaseAPIException):
    """Raised when requested resource is not found"""
    
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_404_NOT_FOUND, details)

class ValidationError(BaseAPIException):
    """Raised when input validation fails"""
    
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)

class ConflictError(BaseAPIException):
    """Raised when resource conflict occurs"""
    
    def __init__(self, message: str = "Resource conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_409_CONFLICT, details)

class RateLimitError(BaseAPIException):
    """Raised when rate limit is exceeded"""
    
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_429_TOO_MANY_REQUESTS, details)

class ServiceUnavailableError(BaseAPIException):
    """Raised when external service is unavailable"""
    
    def __init__(self, message: str = "Service temporarily unavailable", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_503_SERVICE_UNAVAILABLE, details)

# AI-specific exceptions
class AIProcessingError(BaseAPIException):
    """Raised when AI processing fails"""
    
    def __init__(self, message: str = "AI processing failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR, details)

class InsufficientCreditsError(BaseAPIException):
    """Raised when AI service credits are insufficient"""
    
    def __init__(self, message: str = "Insufficient AI credits", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_402_PAYMENT_REQUIRED, details)

# Business logic exceptions
class InternNotFoundError(NotFoundError):
    """Raised when intern is not found"""
    
    def __init__(self, intern_id: int):
        super().__init__(f"Intern with ID {intern_id} not found", {"intern_id": intern_id})

class MentorNotFoundError(NotFoundError):
    """Raised when mentor is not found"""
    
    def __init__(self, mentor_id: int):
        super().__init__(f"Mentor with ID {mentor_id} not found", {"mentor_id": mentor_id})

class TaskNotFoundError(NotFoundError):
    """Raised when task is not found"""
    
    def __init__(self, task_id: int):
        super().__init__(f"Task with ID {task_id} not found", {"task_id": task_id})

class InvalidTaskStatusError(ValidationError):
    """Raised when task status transition is invalid"""
    
    def __init__(self, current_status: str, attempted_status: str):
        super().__init__(
            f"Cannot transition task from {current_status} to {attempted_status}",
            {"current_status": current_status, "attempted_status": attempted_status}
        )

class MentorCapacityExceededError(ConflictError):
    """Raised when mentor capacity is exceeded"""
    
    def __init__(self, mentor_id: int, current_count: int, max_capacity: int):
        super().__init__(
            f"Mentor capacity exceeded. Current: {current_count}, Max: {max_capacity}",
            {"mentor_id": mentor_id, "current_count": current_count, "max_capacity": max_capacity}
        )

class FileUploadError(BaseAPIException):
    """Raised when file upload fails"""
    
    def __init__(self, message: str = "File upload failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_400_BAD_REQUEST, details)

class FileSizeExceededError(FileUploadError):
    """Raised when uploaded file size exceeds limit"""
    
    def __init__(self, file_size: int, max_size: int):
        super().__init__(
            f"File size {file_size} bytes exceeds maximum {max_size} bytes",
            {"file_size": file_size, "max_size": max_size}
        )

class UnsupportedFileTypeError(FileUploadError):
    """Raised when uploaded file type is not supported"""
    
    def __init__(self, file_type: str, supported_types: list):
        super().__init__(
            f"File type {file_type} not supported. Supported types: {supported_types}",
            {"file_type": file_type, "supported_types": supported_types}
        )

# Database exceptions
class DatabaseError(BaseAPIException):
    """Raised when database operation fails"""
    
    def __init__(self, message: str = "Database operation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR, details)

class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails"""
    
    def __init__(self):
        super().__init__(
            "Unable to connect to database",
            {"error_type": "connection_error"}
        )

# External service exceptions
class ExternalServiceError(BaseAPIException):
    """Raised when external service call fails"""
    
    def __init__(self, service_name: str, message: str = "External service error"):
        super().__init__(
            f"{service_name}: {message}",
            status.HTTP_503_SERVICE_UNAVAILABLE,
            {"service_name": service_name}
        )

class OpenAIError(ExternalServiceError):
    """Raised when OpenAI API fails"""
    
    def __init__(self, message: str = "OpenAI API error"):
        super().__init__("OpenAI", message)

class EmailDeliveryError(ExternalServiceError):
    """Raised when email delivery fails"""
    
    def __init__(self, message: str = "Email delivery failed"):
        super().__init__("Email Service", message)

# Exception handlers
async def base_api_exception_handler(request: Request, exc: BaseAPIException):
    """Handle custom API exceptions"""
    
    logger.error(
        f"API Exception: {exc.message}",
        extra={
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.message,
            "details": exc.details,
            "type": exc.__class__.__name__,
            "path": request.url.path,
            "timestamp": "2024-08-09T20:25:00Z"  # Use actual timestamp in production
        }
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle standard HTTP exceptions"""
    
    logger.warning(
        f"HTTP Exception: {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "type": "HTTPException",
            "path": request.url.path,
            "timestamp": "2024-08-09T20:25:00Z"
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    
    logger.warning(
        f"Validation Error: {str(exc)}",
        extra={
            "errors": exc.errors(),
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "message": "Validation failed",
            "details": {
                "validation_errors": exc.errors(),
                "body": exc.body
            },
            "type": "ValidationError",
            "path": request.url.path,
            "timestamp": "2024-08-09T20:25:00Z"
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    
    logger.error(
        f"Unexpected error: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "exception_type": exc.__class__.__name__
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "An unexpected error occurred",
            "type": "InternalServerError",
            "path": request.url.path,
            "timestamp": "2024-08-09T20:25:00Z"
        }
    )

# Utility functions
def raise_for_status_code(status_code: int, message: str = "", details: Optional[Dict[str, Any]] = None):
    """Raise appropriate exception based on status code"""
    
    if status_code == 401:
        raise AuthenticationError(message or "Authentication failed", details)
    elif status_code == 403:
        raise AuthorizationError(message or "Access denied", details)
    elif status_code == 404:
        raise NotFoundError(message or "Resource not found", details)
    elif status_code == 409:
        raise ConflictError(message or "Resource conflict", details)
    elif status_code == 422:
        raise ValidationError(message or "Validation failed", details)
    elif status_code == 429:
        raise RateLimitError(message or "Rate limit exceeded", details)
    elif status_code >= 500:
        raise ServiceUnavailableError(message or "Service unavailable", details)
    else:
        raise BaseAPIException(message or "Unknown error", status_code, details)

def handle_database_error(func):
    """Decorator to handle database errors"""
    
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "connection" in str(e).lower():
                raise DatabaseConnectionError()
            else:
                raise DatabaseError(f"Database operation failed: {str(e)}")
    
    return wrapper

def handle_external_service_error(service_name: str):
    """Decorator to handle external service errors"""
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                raise ExternalServiceError(service_name, str(e))
        return wrapper
    
    return decorator
