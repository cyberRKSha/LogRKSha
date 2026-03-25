# app/services/cache.py
import redis
import json
import functools
import logging
from typing import Optional, Any
from app.config import settings

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self):
        self._redis = None

    @property
    def client(self) -> redis.Redis:
        if self._redis is None:
            try:
                self._redis = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    decode_responses=True # Automatically decode bytes to strings
                )
                self._redis.ping()
                logger.info("✅ Connected to Redis cache service")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._redis = None # Ensure it stays None so we retry or fail gracefully
        return self._redis

    def get_json(self, key: str) -> Optional[Any]:
        """Retrieve and deserialize a JSON value from Redis."""
        client = self.client
        if not client: return None
        
        try:
            val = client.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning(f"Cache GET error for {key}: {e}")
            return None

    def set_json(self, key: str, value: Any, ttl: int = 300):
        """Serialize and store a value as JSON in Redis with TTL."""
        client = self.client
        if not client: return
        
        try:
            client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning(f"Cache SET error for {key}: {e}")

    def memoize(self, ttl: int = 300, key_prefix: str = "", exclude_types: tuple = ()):
        """
        Decorator to cache function results. 
        exclude_types: Tuple of types to ignore in key generation (e.g., (Request, BackgroundTasks, Session))
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Filter args and kwargs for key generation
                filtered_args = [a for a in args if not isinstance(a, exclude_types)]
                filtered_kwargs = {k: v for k, v in kwargs.items() if not isinstance(v, exclude_types)}
                
                arg_str = ":".join([str(a) for a in filtered_args])
                kwarg_str = ":".join([f"{k}={v}" for k, v in filtered_kwargs.items()])
                
                cache_key = f"{key_prefix}:{func.__name__}:{arg_str}:{kwarg_str}"
                
                cached_val = self.get_json(cache_key)
                if cached_val is not None:
                    return cached_val
                
                # Call original function
                result = await func(*args, **kwargs)
                
                # Cache result
                if result is not None:
                    self.set_json(cache_key, result, ttl)
                
                return result
            return wrapper
        return decorator

    def get_cached_ip_intel(self, ip: str) -> Optional[dict]:
        return self.get_json(f"intel:{ip}")

    def set_cached_ip_intel(self, ip: str, data: dict, ttl: int = 86400): # 24 hour TTL for IP intel
        self.set_json(f"intel:{ip}", data, ttl)

cache = RedisCache()
