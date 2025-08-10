import logging
import logging.config
import time
import os
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import psutil
import uvicorn
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.core.exceptions import (
    BaseAPIException,
    base_api_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)

# Import API routers
from app.api.v1 import (
    auth, 
    interns, 
    mentors, 
    tasks, 
    ai_agents, 
    learning, 
    analytics
)
from app.api.v1.websocket import router as websocket_router

# Enhanced middleware classes
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add comprehensive security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'"
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enhanced rate limiting middleware with IP tracking"""
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        now = time.time()
        
        # Initialize client if not exists
        if client_ip not in self.clients:
            self.clients[client_ip] = []
        
        # Clean old requests
        self.clients[client_ip] = [
            req_time for req_time in self.clients[client_ip]
            if now - req_time < self.period
        ]
        
        # Check rate limit
        if len(self.clients[client_ip]) >= self.calls:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {self.calls} requests per {self.period} seconds allowed",
                    "retry_after": self.period
                }
            )
        
        # Record this request
        self.clients[client_ip].append(now)
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(self.calls - len(self.clients[client_ip]))
        response.headers["X-RateLimit-Reset"] = str(int(now + self.period))
        
        return response

class LoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced request/response logging middleware"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url} - "
            f"IP: {request.client.host} - "
            f"User-Agent: {request.headers.get('user-agent', 'Unknown')}"
        )
        
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        logger.info(
            f"Response: {response.status_code} - "
            f"Time: {process_time:.4f}s - "
            f"IP: {request.client.host}"
        )
        
        response.headers["X-Process-Time"] = str(process_time)
        return response

# Setup comprehensive logging
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
            }
        },
        "loggers": {
            "app": {
                "handlers": ["console", "file_info", "file_error"],
                "level": "DEBUG" if settings.DEBUG else "INFO",
                "propagate": False
            },
            "ai_service": {
                "handlers": ["console", "file_info"],
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
    return logging.getLogger("app")

# Initialize logging
logger = setup_logging()

# Application startup time
app_start_time = datetime.utcnow()

# Create database tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Failed to create database tables: {e}")

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Powered Virtual Internship Platform Backend - Production Ready",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc"
)

# Application Events
@app.on_event("startup")
async def startup_event():
    """Enhanced application startup tasks"""
    logger.info(f"🚀 Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    
    # Initialize AI services with error handling
    try:
        from app.services.ai_service import ai_service
        health = await ai_service.get_ai_service_health()
        if health["status"] == "healthy":
            logger.info("✅ AI services initialized successfully")
        else:
            logger.warning("⚠️ AI services initialized with warnings")
    except Exception as e:
        logger.error(f"❌ Failed to initialize AI services: {e}")
    
    # Test database connectivity
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("✅ Database connection established")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
    
    # Create necessary directories
    for directory in ["logs", "uploads", "backups"]:
        Path(directory).mkdir(exist_ok=True)
    
    logger.info("🎯 Application startup completed successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Enhanced application shutdown tasks"""
    uptime = datetime.utcnow() - app_start_time
    logger.info(f"🛑 Shutting down {settings.PROJECT_NAME}")
    logger.info(f"⏱️ Total uptime: {uptime}")
    
    # Log final statistics
    try:
        from app.services.ai_service import ai_service
        credits = await ai_service.check_ai_credits()
        logger.info(f"📊 AI Service Stats - Requests: {credits['total_requests']}, Cost: ${credits['total_cost']}")
    except Exception as e:
        logger.warning(f"Failed to get final AI stats: {e}")

# Exception handlers
app.add_exception_handler(BaseAPIException, base_api_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Enhanced Middleware Stack (order matters!)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, calls=100, period=60)
app.add_middleware(LoggingMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.yourdomain.com", "yourdomain.com", "*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (if needed)
if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routers
app.include_router(
    auth.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["Authentication"]
)

app.include_router(
    interns.router,
    prefix=f"{settings.API_V1_STR}/interns",
    tags=["Interns"]
)

app.include_router(
    mentors.router,
    prefix=f"{settings.API_V1_STR}/mentors",
    tags=["Mentors"]
)

app.include_router(
    tasks.router,
    prefix=f"{settings.API_V1_STR}/tasks",
    tags=["Tasks"]
)

app.include_router(
    ai_agents.router,
    prefix=f"{settings.API_V1_STR}/ai",
    tags=["AI Agents"]
)

app.include_router(
    learning.router,
    prefix=f"{settings.API_V1_STR}/learning",
    tags=["Learning"]
)

app.include_router(
    analytics.router,
    prefix=f"{settings.API_V1_STR}/analytics",
    tags=["Analytics"]
)

# WebSocket router
app.include_router(
    websocket_router,
    prefix=f"{settings.API_V1_STR}",
    tags=["WebSocket"]
)

# Enhanced Health Check Endpoints
@app.get("/")
async def root():
    """Enhanced root endpoint with comprehensive API information"""
    uptime = datetime.utcnow() - app_start_time
    
    return {
        "message": "AI Virtual Intern Platform API",
        "version": settings.VERSION,
        "status": "active",
        "environment": settings.ENVIRONMENT,
        "uptime": str(uptime),
        "features": [
            "🔐 Authentication & Authorization",
            "👨‍🎓 Intern Management",
            "👨‍🏫 Mentor System",
            "📋 Task Management", 
            "🤖 AI Agents",
            "📚 Learning Management",
            "📊 Analytics & Reporting",
            "🔄 Real-time Communication",
            "🛡️ Security & Rate Limiting",
            "📈 Monitoring & Logging"
        ],
        "endpoints": {
            "docs": f"{settings.API_V1_STR}/docs",
            "redoc": f"{settings.API_V1_STR}/redoc",
            "health": "/health",
            "metrics": "/metrics"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Comprehensive health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime": str(datetime.utcnow() - app_start_time),
        "checks": {}
    }
    
    # Database health check
    try:
        db.execute("SELECT 1")
        health_status["checks"]["database"] = {
            "status": "healthy",
            "response_time_ms": 0  # You could measure actual response time
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # AI service health check
    try:
        from app.services.ai_service import get_ai_service_health
        ai_health = await get_ai_service_health()
        health_status["checks"]["ai_service"] = ai_health
        if ai_health["status"] != "healthy":
            health_status["status"] = "degraded"
    except Exception as e:
        logger.error(f"AI service health check failed: {e}")
        health_status["checks"]["ai_service"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # File system health check
    try:
        test_file = Path("logs") / "health_check.tmp"
        test_file.write_text("health_check")
        test_file.unlink()
        health_status["checks"]["filesystem"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Filesystem health check failed: {e}")
        health_status["checks"]["filesystem"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/metrics")
async def metrics():
    """Comprehensive system metrics endpoint for monitoring"""
    try:
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Application metrics
        uptime = datetime.utcnow() - app_start_time
        
        # AI service metrics
        try:
            from app.services.ai_service import ai_service
            ai_credits = await ai_service.check_ai_credits()
        except Exception as e:
            logger.warning(f"Failed to get AI metrics: {e}")
            ai_credits = {"error": "AI metrics unavailable"}
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "cpu_percent": round(cpu_percent, 2),
                "memory_percent": round(memory.percent, 2),
                "memory_available_mb": round(memory.available / 1024 / 1024, 2),
                "memory_used_mb": round(memory.used / 1024 / 1024, 2),
                "disk_percent": round(disk.percent, 2),
                "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 2)
            },
            "application": {
                "version": settings.VERSION,
                "environment": settings.ENVIRONMENT,
                "uptime_seconds": int(uptime.total_seconds()),
                "uptime_human": str(uptime),
                "start_time": app_start_time.isoformat()
            },
            "ai_service": ai_credits,
            "features": {
                "debug_mode": settings.DEBUG,
                "rate_limiting": True,
                "security_headers": True,
                "logging": True,
                "monitoring": True
            }
        }
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        raise HTTPException(status_code=503, detail="Metrics temporarily unavailable")

@app.get("/status")
async def status():
    """Quick status endpoint for load balancer health checks"""
    return {
        "status": "ok",
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }

# Production readiness check endpoint
@app.get("/readiness")
async def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes-style readiness probe"""
    try:
        # Quick database check
        db.execute("SELECT 1")
        
        # Check critical directories exist
        required_dirs = ["logs", "uploads"]
        for dir_name in required_dirs:
            if not Path(dir_name).exists():
                raise Exception(f"Required directory {dir_name} not found")
        
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")

# Liveness probe for Kubernetes
@app.get("/liveness")
async def liveness_check():
    """Kubernetes-style liveness probe"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0", 
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
        access_log=True
    )
