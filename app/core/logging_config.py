import logging
import logging.config
import logging.handlers
import os
import sys
from pathlib import Path
from pythonjsonlogger import jsonlogger
import structlog
from app.core.config import settings

def setup_production_logging():
    """Setup comprehensive production logging"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Custom JSON formatter
    class CustomJsonFormatter(jsonlogger.JsonFormatter):
        def add_fields(self, log_record, record, message_dict):
            super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
            log_record['timestamp'] = record.created
            log_record['level'] = record.levelname
            log_record['logger'] = record.name
            log_record['module'] = record.module
            log_record['function'] = record.funcName
            log_record['line'] = record.lineno
            
            # Add request context if available
            if hasattr(record, 'request_id'):
                log_record['request_id'] = record.request_id
            if hasattr(record, 'user_id'):
                log_record['user_id'] = record.user_id
    
    # Structured logging configuration
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(funcName)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "json": {
                "()": CustomJsonFormatter,
                "format": "%(timestamp)s %(level)s %(name)s %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "default",
                "stream": sys.stdout
            },
            "file_info": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filename": log_dir / "app.log",
                "maxBytes": 50 * 1024 * 1024,  # 50MB
                "backupCount": 10
            },
            "file_error": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": log_dir / "error.log",
                "maxBytes": 50 * 1024 * 1024,
                "backupCount": 5
            },
            "ai_service": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": log_dir / "ai_service.log",
                "maxBytes": 50 * 1024 * 1024,
                "backupCount": 5
            },
            "security": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "WARNING",
                "formatter": "json",
                "filename": log_dir / "security.log",
                "maxBytes": 50 * 1024 * 1024,
                "backupCount": 10
            },
            "performance": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": log_dir / "performance.log",
                "maxBytes": 50 * 1024 * 1024,
                "backupCount": 5
            }
        },
        "loggers": {
            "app": {
                "handlers": ["console", "file_info", "file_error"],
                "level": "DEBUG" if settings.DEBUG else "INFO",
                "propagate": False
            },
            "ai_service": {
                "handlers": ["ai_service", "console"],
                "level": "INFO",
                "propagate": False
            },
            "security": {
                "handlers": ["security", "console"],
                "level": "WARNING",
                "propagate": False
            },
            "performance": {
                "handlers": ["performance"],
                "level": "INFO",
                "propagate": False
            },
            "uvicorn": {
                "handlers": ["console", "file_info"],
                "level": "INFO",
                "propagate": False
            },
            "uvicorn.access": {
                "handlers": ["file_info"],
                "level": "INFO",
                "propagate": False
            },
            "sqlalchemy.engine": {
                "handlers": ["file_info"],
                "level": "WARNING",
                "propagate": False
            }
        },
        "root": {
            "handlers": ["console", "file_info", "file_error"],
            "level": "INFO"
        }
    }
    
    # Apply logging configuration
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Configure structlog for structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.DEBUG else logging.INFO
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Create specialized loggers
    loggers = {
        "app": logging.getLogger("app"),
        "ai_service": logging.getLogger("ai_service"),
        "security": logging.getLogger("security"),
        "performance": logging.getLogger("performance"),
        "database": logging.getLogger("database"),
        "websocket": logging.getLogger("websocket")
    }
    
    return loggers

class RequestContextFilter(logging.Filter):
    """Add request context to log records"""
    
    def filter(self, record):
        # Add request ID and user ID if available in context
        from contextvars import ContextVar
        
        request_id: ContextVar[str] = ContextVar('request_id', default=None)
        user_id: ContextVar[int] = ContextVar('user_id', default=None)
        
        record.request_id = request_id.get()
        record.user_id = user_id.get()
        
        return True

# Performance logging decorator
def log_performance(operation_name: str):
    """Decorator to log operation performance"""
    def decorator(func):
        import functools
        import time
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            logger = logging.getLogger("performance")
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    f"Operation completed",
                    extra={
                        "operation": operation_name,
                        "duration_ms": round(duration * 1000, 2),
                        "status": "success"
                    }
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    f"Operation failed",
                    extra={
                        "operation": operation_name,
                        "duration_ms": round(duration * 1000, 2),
                        "status": "error",
                        "error": str(e)
                    }
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            logger = logging.getLogger("performance")
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    f"Operation completed",
                    extra={
                        "operation": operation_name,
                        "duration_ms": round(duration * 1000, 2),
                        "status": "success"
                    }
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    f"Operation failed",
                    extra={
                        "operation": operation_name,
                        "duration_ms": round(duration * 1000, 2),
                        "status": "error",
                        "error": str(e)
                    }
                )
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
