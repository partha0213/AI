import json
import hashlib
import pickle
import asyncio
from typing import Any, Optional, Dict, Callable
from functools import wraps
import redis.asyncio as redis
from datetime import datetime, timedelta
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Production-ready caching service with Redis"""
    
    def __init__(self):
        self.redis_client = None
        self.local_cache = {}  # Fallback for when Redis is unavailable
        self.local_cache_max_size = 1000
        
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False,  # Handle bytes manually for pickle
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Redis cache service initialized successfully")
            
        except Exception as e:
            logger.warning(f"Redis unavailable, falling back to local cache: {e}")
            self.redis_client = None
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        try:
            if self.redis_client:
                # Try Redis first
                value = await self.redis_client.get(key)
                if value is not None:
                    try:
                        return pickle.loads(value)
                    except:
                        # Fallback to JSON
                        return json.loads(value.decode('utf-8'))
            
            # Fallback to local cache
            return self.local_cache.get(key, default)
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        serialize_method: str = "pickle"
    ) -> bool:
        """Set value in cache"""
        try:
            # Serialize value
            if serialize_method == "pickle":
                serialized_value = pickle.dumps(value)
            else:
                serialized_value = json.dumps(value, default=str).encode('utf-8')
            
            if self.redis_client:
                # Set in Redis
                if ttl:
                    await self.redis_client.setex(key, ttl, serialized_value)
                else:
                    await self.redis_client.set(key, serialized_value)
                return True
            
            # Fallback to local cache
            self._manage_local_cache_size()
            self.local_cache[key] = value
            
            # Simple TTL simulation for local cache
            if ttl:
                asyncio.create_task(self._expire_local_key(key, ttl))
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            deleted = False
            
            if self.redis_client:
                result = await self.redis_client.delete(key)
                deleted = result > 0
            
            if key in self.local_cache:
                del self.local_cache[key]
                deleted = True
            
            return deleted
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            if self.redis_client:
                return await self.redis_client.exists(key)
            
            return key in self.local_cache
            
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def cache_ai_response(
        self, 
        prompt: str, 
        model: str, 
        response: Dict[str, Any], 
        ttl: int = 3600
    ) -> bool:
        """Cache AI response with prompt hash"""
        
        # Create cache key from prompt and model
        prompt_hash = hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()
        cache_key = f"ai_response:{prompt_hash}"
        
        # Add metadata
        cached_response = {
            "response": response,
            "model": model,
            "prompt_hash": prompt_hash,
            "cached_at": datetime.utcnow().isoformat(),
            "ttl": ttl
        }
        
        return await self.set(cache_key, cached_response, ttl)
    
    async def get_cached_ai_response(
        self, 
        prompt: str, 
        model: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached AI response"""
        
        prompt_hash = hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()
        cache_key = f"ai_response:{prompt_hash}"
        
        cached_data = await self.get(cache_key)
        
        if cached_data:
            # Check if cache is still valid
            cached_at = datetime.fromisoformat(cached_data["cached_at"])
            ttl = cached_data["ttl"]
            
            if datetime.utcnow() - cached_at < timedelta(seconds=ttl):
                logger.info(f"Cache hit for AI response: {prompt_hash[:8]}...")
                return cached_data["response"]
            else:
                # Cache expired, delete it
                await self.delete(cache_key)
        
        return None
    
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Increment counter in cache"""
        try:
            if self.redis_client:
                value = await self.redis_client.incr(key, amount)
                if ttl:
                    await self.redis_client.expire(key, ttl)
                return value
            
            # Local cache fallback
            current = self.local_cache.get(key, 0)
            new_value = current + amount
            self.local_cache[key] = new_value
            return new_value
            
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "redis_available": self.redis_client is not None,
            "local_cache_size": len(self.local_cache)
        }
        
        if self.redis_client:
            try:
                info = await self.redis_client.info()
                stats.update({
                    "redis_memory_usage": info.get('used_memory_human', 'unknown'),
                    "redis_connected_clients": info.get('connected_clients', 0),
                    "redis_keyspace_hits": info.get('keyspace_hits', 0),
                    "redis_keyspace_misses": info.get('keyspace_misses', 0)
                })
                
                # Calculate hit rate
                hits = info.get('keyspace_hits', 0)
                misses = info.get('keyspace_misses', 0)
                total = hits + misses
                
                if total > 0:
                    stats["redis_hit_rate"] = round((hits / total) * 100, 2)
                
            except Exception as e:
                logger.error(f"Failed to get Redis stats: {e}")
        
        return stats
    
    def _manage_local_cache_size(self):
        """Manage local cache size to prevent memory issues"""
        if len(self.local_cache) >= self.local_cache_max_size:
            # Remove oldest 10% of entries (simple LRU simulation)
            keys_to_remove = list(self.local_cache.keys())[:int(self.local_cache_max_size * 0.1)]
            for key in keys_to_remove:
                self.local_cache.pop(key, None)
    
    async def _expire_local_key(self, key: str, ttl: int):
        """Expire local cache key after TTL"""
        await asyncio.sleep(ttl)
        self.local_cache.pop(key, None)

# Cache decorator for functions
def cache_result(ttl: int = 3600, key_prefix: str = ""):
    """Decorator to cache function results"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            key_data = f"{key_prefix}:{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.sha256(key_data.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = await cache_service.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_service.set(cache_key, result, ttl)
            
            logger.debug(f"Cache miss for {func.__name__}, result cached")
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, use asyncio to run async cache operations
            loop = asyncio.get_event_loop()
            
            # Generate cache key
            key_data = f"{key_prefix}:{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.sha256(key_data.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = loop.run_until_complete(cache_service.get(cache_key))
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            loop.run_until_complete(cache_service.set(cache_key, result, ttl))
            
            logger.debug(f"Cache miss for {func.__name__}, result cached")
            return result
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Global cache service instance
cache_service = CacheService()
