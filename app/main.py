import logging
import logging.config
import time
import os
import asyncio
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import psutil
import uvicorn
from sqlalchemy.orm import Session
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.core.exceptions import (
    BaseAPIException,
    base_api_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from app.core.logging_config import setup_production_logging
from app.core.security import security_validator, rate_limiter
from app.services.cache_service import cache_service
from monitoring.health_checks import health_checker
from app.services.ai_circuit_breaker import openai_circuit_breaker

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

# Application startup time
app_start_time = datetime.utcnow()

# Setup logging first
loggers = setup_production_logging()
logger = loggers["app"]

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
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https:"
        )
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enhanced rate limiting middleware with different tiers"""
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        
        # Determine rate limit tier based on endpoint
        tier = "standard"
        if "/ai/" in str(request.url):
            tier = "ai_heavy"
        elif request.method in ["POST", "PUT", "DELETE"]:
            tier = "premium"
        
        # Check rate limit
        if not rate_limiter.is_allowed(client_ip, tier):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}, tier: {tier}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum requests per hour exceeded for tier: {tier}",
                    "retry_after": 3600
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = rate_limiter.rate_limits[tier]['requests'] - len(rate_limiter.client_requests.get(client_ip, []))
        response.headers["X-RateLimit-Limit"] = str(rate_limiter.rate_limits[tier]['requests'])
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + rate_limiter.rate_limits[tier]['window']))
        
        return response

class LoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced request/response logging middleware with performance tracking"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = f"req_{int(start_time * 1000000)}"
        
        # Log request
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "ip": request.client.host,
                "user_agent": request.headers.get("user-agent", "Unknown")
            }
        )
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
            
            # Log response
            process_time = time.time() - start_time
            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": round(process_time * 1000, 2),
                    "ip": request.client.host
                }
            )
            
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(round(process_time, 4))
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "duration_ms": round(process_time * 1000, 2),
                    "ip": request.client.host
                },
                exc_info=True
            )
            raise

# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enhanced application lifespan management"""
    
    # Startup
    logger.info(f"🚀 Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    
    try:
        # Create necessary directories
        for directory in ["logs", "uploads", "backups", "temp"]:
            Path(directory).mkdir(exist_ok=True)
        
        # Initialize services
        await cache_service.initialize()
        await health_checker.initialize()
        
        # Test database connectivity
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("✅ Database connection established")
        
        # Initialize AI services
        from app.services.ai_service import ai_service
        health = await ai_service.get_ai_service_health()
        if health["status"] == "healthy":
            logger.info("✅ AI services initialized successfully")
        else:
            logger.warning("⚠️ AI services initialized with warnings")
        
        # Create database tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables verified")
        
        logger.info("🎯 Application startup completed successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        raise
    
    # Shutdown
    uptime = datetime.utcnow() - app_start_time
    logger.info(f"🛑 Shutting down {settings.PROJECT_NAME}")
    logger.info(f"⏱️ Total uptime: {uptime}")
    
    try:
        # Get final statistics
        from app.services.ai_service import ai_service
        credits = await ai_service.check_ai_credits()
        logger.info(f"📊 Final AI Stats - Requests: {credits['total_requests']}, Cost: ${credits['total_cost']}")
        
        # Close connections
        if cache_service.redis_client:
            await cache_service.redis_client.close()
        
        logger.info("✅ Graceful shutdown completed")
        
    except Exception as e:
        logger.warning(f"⚠️ Shutdown warning: {e}")

# Initialize FastAPI app with enhanced configuration
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Powered Virtual Internship Platform Backend - Production Ready",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# Exception handlers
app.add_exception_handler(BaseAPIException, base_api_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Enhanced Middleware Stack (order matters!)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, calls=100, period=3600)
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

# Static files
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

# Enhanced Health Check and Monitoring Endpoints
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
            "🤖 AI Agents with Circuit Breakers",
            "📚 Learning Management",
            "📊 Analytics & Reporting",
            "🔄 Real-time Communication",
            "🛡️ Security & Rate Limiting",
            "📈 Monitoring & Logging",
            "🚀 Background Task Processing",
            "💾 Redis Caching",
            "🔍 Comprehensive Health Checks"
        ],
        "endpoints": {
            "docs": f"{settings.API_V1_STR}/docs",
            "redoc": f"{settings.API_V1_STR}/redoc",
            "health": "/health",
            "metrics": "/metrics",
            "prometheus": "/prometheus"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    
    try:
        health_data = await health_checker.comprehensive_health_check()
        
        # Add circuit breaker status
        health_data["circuit_breakers"] = {
            "openai": openai_circuit_breaker.get_status()
        }
        
        # Add cache status
        cache_stats = await cache_service.get_stats()
        health_data["cache"] = cache_stats
        
        # Determine HTTP status code based on health
        status_code = 200
        if health_data["status"] == "degraded":
            status_code = 503
        elif health_data["status"] == "unhealthy":
            status_code = 503
        
        return JSONResponse(content=health_data, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            },
            status_code=503
        )

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
        from app.services.ai_service import ai_service
        ai_credits = await ai_service.check_ai_credits()
        
        # Cache metrics
        cache_stats = await cache_service.get_stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "cpu_percent": round(cpu_percent, 2),
                "memory_percent": round(memory.percent, 2),
                "memory_available_mb": round(memory.available / 1024 / 1024, 2),
                "memory_used_mb": round(memory.used / 1024 / 1024, 2),
                "disk_percent": round(disk.percent, 2),
                "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "load_average": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None
            },
            "application": {
                "version": settings.VERSION,
                "environment": settings.ENVIRONMENT,
                "uptime_seconds": int(uptime.total_seconds()),
                "uptime_human": str(uptime),
                "start_time": app_start_time.isoformat()
            },
            "ai_service": ai_credits,
            "cache": cache_stats,
            "circuit_breakers": {
                "openai": openai_circuit_breaker.get_status()
            }
        }
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        raise HTTPException(status_code=503, detail="Metrics temporarily unavailable")

@app.get("/prometheus")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    try:
        from monitoring.health_checks import generate_latest
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Prometheus metrics failed: {e}")
        raise HTTPException(status_code=503, detail="Prometheus metrics unavailable")

@app.get("/status")
async def status():
    """Quick status endpoint for load balancer health checks"""
    return {
        "status": "ok",
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }

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
        
        # Check AI service
        from app.services.ai_service import ai_service
        ai_health = await ai_service.get_ai_service_health()
        if ai_health["status"] == "unhealthy":
            raise Exception("AI service not ready")
        
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")

@app.get("/liveness")
async def liveness_check():
    """Kubernetes-style liveness probe"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}

# Development endpoint (only in debug mode)
if settings.DEBUG:
    @app.get("/debug/info")
    async def debug_info():
        """Debug information endpoint (only available in debug mode)"""
        return {
            "settings": {
                "database_url": settings.DATABASE_URL[:50] + "..." if settings.DATABASE_URL else None,
                "redis_url": settings.REDIS_URL[:50] + "..." if settings.REDIS_URL else None,
                "environment": settings.ENVIRONMENT,
                "debug": settings.DEBUG
            },
            "system": {
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "platform": platform.platform(),
                "process_id": os.getpid()
            }
        }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0", 
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
        access_log=True
    )
