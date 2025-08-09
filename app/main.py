import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.analytics_service import get_system_health_metrics
from app.core.database import get_db
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from app.core.config import settings
from app.core.database import engine, Base
from app.core.exceptions import (
    BaseAPIException,
    base_api_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)

# Import all API routers
from app.api.v1 import (
    auth, 
    interns, 
    mentors, 
    tasks, 
    ai_agents, 
    learning, 
    analytics,
    # Add these if they exist:
    # feedback,
    # notifications
)
from app.api.v1.websocket import router as websocket_router

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Powered Virtual Internship Platform Backend",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc"
)

# Application Events
@app.on_event("startup")
async def startup_event():
    """Application startup tasks"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    
    # Initialize AI services
    try:
        from app.services.ai_service import ai_service
        logger.info("AI services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize AI services: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks"""
    logger = logging.getLogger(__name__)
    logger.info(f"Shutting down {settings.PROJECT_NAME}")

# Exception handlers
app.add_exception_handler(BaseAPIException, base_api_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.yourdomain.com", "your-domain.com"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (if needed)
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

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

# Add these if you have the routers:
# app.include_router(
#     feedback.router,
#     prefix=f"{settings.API_V1_STR}/feedback",
#     tags=["Feedback"]
# )

# app.include_router(
#     notifications.router,
#     prefix=f"{settings.API_V1_STR}/notifications",
#     tags=["Notifications"]
# )

# WebSocket router
app.include_router(
    websocket_router,
    prefix=f"{settings.API_V1_STR}",
    tags=["WebSocket"]
)

# Health Check endpoints
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "AI Virtual Intern Platform API",
        "version": settings.VERSION,
        "status": "active",
        "environment": settings.ENVIRONMENT,
        "features": [
            "Authentication & Authorization",
            "Intern Management",
            "Mentor System",
            "Task Management", 
            "AI Agents",
            "Learning Management",
            "Analytics & Reporting",
            "Real-time Communication"
        ],
        "docs_url": f"{settings.API_V1_STR}/docs",
        "redoc_url": f"{settings.API_V1_STR}/redoc"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }

@app.get("/metrics")
async def metrics(db: Session = Depends(get_db)):
    """Comprehensive metrics endpoint"""
    try:
        # Calculate actual uptime
        import psutil
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.utcnow() - boot_time
        
        # Database health check
        try:
            db.execute("SELECT 1")
            db_status = "connected"
        except:
            db_status = "disconnected"
        
        # AI service status
        from app.services.ai_service import ai_service
        ai_credits = await ai_service.check_ai_credits()
        
        return {
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_human": str(uptime),
            "database_status": db_status,
            "ai_service_status": "active",
            "ai_usage": ai_credits,
            "memory_usage": psutil.virtual_memory().percent,
            "cpu_usage": psutil.cpu_percent(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
