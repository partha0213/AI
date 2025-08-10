import logging
import logging.handlers
import os
from pathlib import Path
from app.core.config import settings

def setup_logging():
    """Setup comprehensive logging configuration"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Logging configuration
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "json": {
                "format": '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}',
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "default",
                "stream": "ext://sys.stdout"
            },
            "file_info": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filename": log_dir / "app.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5
            },
            "file_error": {
                "class": "logging.handlers.RotatingFileHandler", 
                "level": "ERROR",
                "formatter": "detailed",
                "filename": log_dir / "error.log",
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 3
            },
            "ai_service": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO", 
                "formatter": "json",
                "filename": log_dir / "ai_service.log",
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 3
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
            "uvicorn": {
                "handlers": ["console"],
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
    
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Create application loggers
    loggers = {
        "app": logging.getLogger("app"),
        "ai_service": logging.getLogger("ai_service"),
        "database": logging.getLogger("database"),
        "websocket": logging.getLogger("websocket")
    }
    
    return loggers
