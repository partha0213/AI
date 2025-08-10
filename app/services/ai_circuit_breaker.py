import asyncio
import time
import logging
from typing import Callable, Any, Dict
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class AICircuitBreaker:
    """Circuit breaker pattern for AI services"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 300,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.next_attempt_time = None
        
    async def call(self, func: Callable, fallback_func: Callable = None, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker moving to HALF_OPEN state")
            else:
                logger.warning("Circuit breaker is OPEN, using fallback")
                if fallback_func:
                    return await fallback_func(*args, **kwargs)
                else:
                    raise Exception("Service temporarily unavailable")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            logger.error(f"Circuit breaker recorded failure: {str(e)}")
            
            if fallback_func:
                return await fallback_func(*args, **kwargs)
            else:
                raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        return (
            self.next_attempt_time is not None and
            datetime.utcnow() >= self.next_attempt_time
        )
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.next_attempt_time = None
        logger.debug("Circuit breaker: Success recorded")
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.next_attempt_time = datetime.utcnow() + timedelta(seconds=self.timeout_seconds)
            logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "next_attempt_time": self.next_attempt_time.isoformat() if self.next_attempt_time else None
        }

# Global circuit breaker instances for different services
openai_circuit_breaker = AICircuitBreaker(failure_threshold=3, timeout_seconds=300)
database_circuit_breaker = AICircuitBreaker(failure_threshold=5, timeout_seconds=60)
