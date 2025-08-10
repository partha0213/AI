import asyncio
import psutil
import time
import logging
from typing import Dict, Any
from sqlalchemy import text
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import redis.asyncio as redis

from app.core.database import engine
from app.core.config import settings

logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('app_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('app_request_duration_seconds', 'Request duration')
AI_REQUEST_COUNT = Counter('ai_requests_total', 'Total AI requests', ['model', 'status'])
AI_RESPONSE_TIME = Histogram('ai_response_time_seconds', 'AI response time')
ACTIVE_CONNECTIONS = Gauge('app_active_connections', 'Active database connections')
SYSTEM_CPU = Gauge('system_cpu_percent', 'System CPU usage')
SYSTEM_MEMORY = Gauge('system_memory_percent', 'System memory usage')

class HealthChecker:
    """Comprehensive health checking system"""
    
    def __init__(self):
        self.redis_client = None
        
    async def initialize(self):
        """Initialize health checker"""
        try:
            self.redis_client = redis.Redis.from_url(settings.REDIS_URL)
        except Exception as e:
            logger.warning(f"Redis not available for health checks: {e}")
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            
            with engine.connect() as conn:
                # Test basic connectivity
                result = conn.execute(text("SELECT 1"))
                
                # Test write capability
                conn.execute(text("CREATE TEMP TABLE health_check (id INT)"))
                conn.execute(text("INSERT INTO health_check VALUES (1)"))
                conn.execute(text("DROP TABLE health_check"))
                
                # Get connection pool status
                pool = engine.pool
                pool_status = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalid": pool.invalid()
                }
            
            response_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "pool_status": pool_status
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        if not self.redis_client:
            return {"status": "not_configured"}
        
        try:
            start_time = time.time()
            
            # Test basic connectivity
            await self.redis_client.ping()
            
            # Test read/write
            test_key = "health_check:test"
            await self.redis_client.set(test_key, "test_value", ex=10)
            value = await self.redis_client.get(test_key)
            await self.redis_client.delete(test_key)
            
            if value.decode() != "test_value":
                raise Exception("Redis read/write test failed")
            
            response_time = time.time() - start_time
            
            # Get Redis info
            info = await self.redis_client.info()
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "memory_usage_mb": round(info.get('used_memory', 0) / 1024 / 1024, 2),
                "connected_clients": info.get('connected_clients', 0)
            }
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_ai_service(self) -> Dict[str, Any]:
        """Check AI service connectivity"""
        try:
            from app.services.ai_service import ai_service
            health_data = await ai_service.get_ai_service_health()
            return health_data
            
        except Exception as e:
            logger.error(f"AI service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Update Prometheus metrics
            SYSTEM_CPU.set(cpu_percent)
            SYSTEM_MEMORY.set(memory.percent)
            
            return {
                "status": "healthy",
                "cpu_percent": round(cpu_percent, 2),
                "memory_percent": round(memory.percent, 2),
                "memory_available_gb": round(memory.available / 1024 / 1024 / 1024, 2),
                "disk_percent": round(disk.percent, 2),
                "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "load_average": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None
            }
            
        except Exception as e:
            logger.error(f"System resource check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """Run all health checks"""
        start_time = time.time()
        
        # Run all checks concurrently
        database_task = asyncio.create_task(self.check_database())
        redis_task = asyncio.create_task(self.check_redis())
        ai_service_task = asyncio.create_task(self.check_ai_service())
        
        # Wait for all checks
        database_health = await database_task
        redis_health = await redis_task
        ai_service_health = await ai_service_task
        system_health = self.check_system_resources()
        
        # Determine overall status
        all_checks = [database_health, redis_health, ai_service_health, system_health]
        unhealthy_checks = [check for check in all_checks if check.get("status") != "healthy"]
        
        overall_status = "healthy" if not unhealthy_checks else "degraded"
        if len(unhealthy_checks) >= 2:
            overall_status = "unhealthy"
        
        total_time = time.time() - start_time
        
        return {
            "status": overall_status,
            "timestamp": time.time(),
            "total_check_time_ms": round(total_time * 1000, 2),
            "checks": {
                "database": database_health,
                "redis": redis_health,
                "ai_service": ai_service_health,
                "system": system_health
            },
            "summary": {
                "total_checks": len(all_checks),
                "healthy_checks": len(all_checks) - len(unhealthy_checks),
                "unhealthy_checks": len(unhealthy_checks)
            }
        }

# Global health checker instance
health_checker = HealthChecker()
