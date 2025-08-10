import psutil
import asyncio
import time
from typing import Dict, Any
from sqlalchemy import text
from datetime import datetime
import logging

from app.core.database import engine
from app.services.ai_service import ai_service
from app.services.ai_circuit_breaker import openai_circuit_breaker

logger = logging.getLogger("app")

class HealthChecker:
    """Comprehensive health checking system for production monitoring"""
    
    def __init__(self):
        self.last_check_time = None
        self.cached_health = None
        self.cache_duration = 30  # Cache health results for 30 seconds
    
    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """Run all health checks with caching for performance"""
        
        # Use cached result if available and recent
        current_time = time.time()
        if (self.cached_health and self.last_check_time and 
            current_time - self.last_check_time < self.cache_duration):
            return self.cached_health
        
        start_time = time.time()
        
        # Run all checks concurrently for better performance
        try:
            database_task = asyncio.create_task(self.check_database())
            ai_service_task = asyncio.create_task(self.check_ai_service())
            system_task = asyncio.create_task(self.check_system_resources())
            
            # Wait for all checks with timeout
            checks = await asyncio.wait_for(
                asyncio.gather(database_task, ai_service_task, system_task, return_exceptions=True),
                timeout=15.0
            )
            
        except asyncio.TimeoutError:
            logger.error("Health check timeout")
            return {
                "status": "unhealthy",
                "error": "Health check timeout",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Process check results
        database_health, ai_health, system_health = checks
        
        # Handle exceptions in individual checks
        if isinstance(database_health, Exception):
            database_health = {"status": "error", "error": str(database_health)}
        if isinstance(ai_health, Exception):
            ai_health = {"status": "error", "error": str(ai_health)}
        if isinstance(system_health, Exception):
            system_health = {"status": "error", "error": str(system_health)}
        
        # Determine overall status
        all_checks = [database_health, ai_health, system_health]
        healthy_checks = sum(1 for check in all_checks if check.get("status") == "healthy")
        total_checks = len(all_checks)
        
        if healthy_checks == total_checks:
            overall_status = "healthy"
        elif healthy_checks >= total_checks * 0.6:  # At least 60% healthy
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        total_check_time = time.time() - start_time
        
        health_result = {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "total_check_time_ms": round(total_check_time * 1000, 2),
            "checks": {
                "database": database_health,
                "ai_service": ai_health,
                "system": system_health
            },
            "circuit_breakers": {
                "openai": openai_circuit_breaker.get_status()
            },
            "summary": {
                "total_checks": total_checks,
                "healthy_checks": healthy_checks,
                "degraded_checks": sum(1 for check in all_checks if check.get("status") == "degraded"),
                "unhealthy_checks": sum(1 for check in all_checks if check.get("status") in ["unhealthy", "error"])
            }
        }
        
        # Cache the result
        self.cached_health = health_result
        self.last_check_time = current_time
        
        return health_result
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            
            # Test basic connectivity
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                
                # Test write capability with temporary table
                conn.execute(text("CREATE TEMP TABLE health_check_temp (id INT)"))
                conn.execute(text("INSERT INTO health_check_temp VALUES (1)"))
                result = conn.execute(text("SELECT COUNT(*) FROM health_check_temp")).fetchone()
                conn.execute(text("DROP TABLE health_check_temp"))
                
                if result[0] != 1:
                    raise Exception("Database write test failed")
                
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
            
            # Determine status based on response time
            if response_time > 5.0:
                status = "degraded"
            elif response_time > 10.0:
                status = "unhealthy"
            else:
                status = "healthy"
            
            return {
                "status": status,
                "response_time_ms": round(response_time * 1000, 2),
                "pool_status": pool_status,
                "connection_test": "passed",
                "write_test": "passed"
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "connection_test": "failed"
            }
    
    async def check_ai_service(self) -> Dict[str, Any]:
        """Check AI service health and circuit breaker status"""
        try:
            # Get AI service health (this includes OpenAI connectivity test)
            ai_health = await ai_service.get_ai_service_health()
            
            # Add additional AI service metrics
            circuit_breaker_status = openai_circuit_breaker.get_status()
            
            # Determine overall AI service status
            if (ai_health.get("status") == "healthy" and 
                circuit_breaker_status.get("state") == "closed"):
                status = "healthy"
            elif (ai_health.get("status") == "healthy" and 
                  circuit_breaker_status.get("state") == "half_open"):
                status = "degraded"
            else:
                status = "unhealthy"
            
            return {
                "status": status,
                "ai_service_health": ai_health,
                "circuit_breaker": circuit_breaker_status,
                "openai_connectivity": ai_health.get("openai_connectivity", "unknown")
            }
            
        except Exception as e:
            logger.error(f"AI service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "ai_service_available": False
            }
    
    async def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            # Get CPU usage (1 second average)
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get memory information
            memory = psutil.virtual_memory()
            
            # Get disk usage
            disk = psutil.disk_usage('/')
            
            # Get load average (if available)
            load_avg = None
            if hasattr(psutil, 'getloadavg'):
                load_avg = psutil.getloadavg()
            
            # Get process information
            current_process = psutil.Process()
            process_memory = current_process.memory_info()
            
            # Determine status based on resource usage
            status = "healthy"
            warnings = []
            
            if cpu_percent > 85:
                status = "degraded"
                warnings.append("High CPU usage")
            elif cpu_percent > 95:
                status = "unhealthy"
                warnings.append("Critical CPU usage")
            
            if memory.percent > 85:
                if status == "healthy":
                    status = "degraded"
                warnings.append("High memory usage")
            elif memory.percent > 95:
                status = "unhealthy"
                warnings.append("Critical memory usage")
            
            if disk.percent > 85:
                if status == "healthy":
                    status = "degraded"
                warnings.append("High disk usage")
            elif disk.percent > 95:
                status = "unhealthy"
                warnings.append("Critical disk usage")
            
            return {
                "status": status,
                "warnings": warnings,
                "cpu_percent": round(cpu_percent, 2),
                "memory": {
                    "percent": round(memory.percent, 2),
                    "available_gb": round(memory.available / 1024 / 1024 / 1024, 2),
                    "used_gb": round(memory.used / 1024 / 1024 / 1024, 2),
                    "total_gb": round(memory.total / 1024 / 1024 / 1024, 2)
                },
                "disk": {
                    "percent": round(disk.percent, 2),
                    "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                    "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                    "total_gb": round(disk.total / 1024 / 1024 / 1024, 2)
                },
                "load_average": list(load_avg) if load_avg else None,
                "process": {
                    "memory_mb": round(process_memory.rss / 1024 / 1024, 2),
                    "memory_percent": round(current_process.memory_percent(), 2)
                }
            }
            
        except Exception as e:
            logger.error(f"System resource check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def quick_health_check(self) -> Dict[str, Any]:
        """Quick health check for load balancer probes"""
        try:
            # Just check if we can connect to database
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            return {
                "status": "ok",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

# Global health checker instance
health_checker = HealthChecker()
