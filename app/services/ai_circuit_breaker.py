import asyncio
import time
import logging
from typing import Callable, Any, Dict
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger("ai_service")

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class AICircuitBreaker:
    """Circuit breaker pattern for AI services with enhanced monitoring"""
    
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
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.next_attempt_time = None
        
        # Metrics
        self.total_requests = 0
        self.total_failures = 0
        self.state_transitions = []
        
    async def call_with_fallback(self, func: Callable, fallback_func: Callable = None, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        
        self.total_requests += 1
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self._record_state_transition("HALF_OPEN")
                logger.info("Circuit breaker moving to HALF_OPEN state")
            else:
                logger.warning("Circuit breaker is OPEN, using fallback")
                if fallback_func:
                    return await fallback_func(*args, **kwargs)
                else:
                    raise Exception("Service temporarily unavailable due to circuit breaker")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            logger.error(f"Circuit breaker recorded failure: {str(e)}")
            
            if fallback_func:
                try:
                    return await fallback_func(*args, **kwargs)
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {str(fallback_error)}")
                    raise e  # Raise original exception
            else:
                raise
        except Exception as e:
            # Unexpected exceptions don't count towards circuit breaker
            logger.error(f"Unexpected error (not counted towards circuit breaker): {str(e)}")
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
        self.success_count += 1
        
        if self.state != CircuitState.CLOSED:
            self.state = CircuitState.CLOSED
            self._record_state_transition("CLOSED")
            logger.info("Circuit breaker CLOSED after successful call")
        
        self.next_attempt_time = None
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                self.state = CircuitState.OPEN
                self._record_state_transition("OPEN")
                logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
            
            self.next_attempt_time = datetime.utcnow() + timedelta(seconds=self.timeout_seconds)
    
    def _record_state_transition(self, new_state: str):
        """Record state transitions for monitoring"""
        self.state_transitions.append({
            "timestamp": datetime.utcnow().isoformat(),
            "state": new_state,
            "failure_count": self.failure_count,
            "success_count": self.success_count
        })
        
        # Keep only last 100 transitions
        if len(self.state_transitions) > 100:
            self.state_transitions = self.state_transitions[-100:]
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        success_rate = 0
        if self.total_requests > 0:
            success_rate = ((self.total_requests - self.total_failures) / self.total_requests) * 100
        
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "success_rate": round(success_rate, 2),
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "next_attempt_time": self.next_attempt_time.isoformat() if self.next_attempt_time else None,
            "timeout_seconds": self.timeout_seconds,
            "recent_state_transitions": self.state_transitions[-10:]  # Last 10 transitions
        }
    
    def reset(self):
        """Manually reset circuit breaker"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.next_attempt_time = None
        self._record_state_transition("RESET")
        logger.info("Circuit breaker manually reset")

# Global circuit breaker instances for different services
openai_circuit_breaker = AICircuitBreaker(failure_threshold=3, timeout_seconds=300)
database_circuit_breaker = AICircuitBreaker(failure_threshold=5, timeout_seconds=60)
redis_circuit_breaker = AICircuitBreaker(failure_threshold=3, timeout_seconds=120)
