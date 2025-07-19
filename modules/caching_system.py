"""
Comprehensive caching system with multiple strategies and Redis support.

This module provides various caching strategies including in-memory, Redis,
and hybrid caching with TTL management, cache invalidation, and performance monitoring.
"""

import asyncio
import json
import logging
import pickle
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import (
    Dict, List, Optional, Any, Union, Callable, TypeVar, Generic,
    Set, Tuple, AsyncGenerator
)
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import hashlib

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

from modules.types import Timestamp, JSONDict, CacheEntry, CacheStrategy
from modules.shared_constants import (
    DEFAULT_CACHE_TTL, LONG_CACHE_TTL, SHORT_CACHE_TTL, MAX_CACHE_SIZE
)
from modules.shared_utilities import SingletonMeta, PerformanceMonitor
from modules.performance_monitor import performance_monitor

logger = logging.getLogger(__name__)

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')


class CacheBackend(Enum):
    """Cache backend types."""
    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"


class CachePolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    FIFO = "fifo"  # First In First Out


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    size: int = 0
    memory_usage_bytes: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


@dataclass
class CacheConfig:
    """Cache configuration."""
    backend: CacheBackend = CacheBackend.MEMORY
    policy: CachePolicy = CachePolicy.LRU
    max_size: int = MAX_CACHE_SIZE
    default_ttl: int = DEFAULT_CACHE_TTL
    redis_url: Optional[str] = None
    redis_db: int = 0
    key_prefix: str = "bot_cache"
    serialization: str = "json"  # json, pickle
    compression: bool = False
    monitoring: bool = True


class CacheInterface(ABC, Generic[K, V]):
    """Abstract cache interface."""
    
    @abstractmethod
    async def get(self, key: K) -> Optional[V]:
        """Get value by key."""
        pass
    
    @abstractmethod
    async def set(self, key: K, value: V, ttl: Optional[int] = None) -> None:
        """Set value with optional TTL."""
        pass
    
    @abstractmethod
    async def delete(self, key: K) -> bool:
        """Delete key and return True if existed."""
        pass
    
    @abstractmethod
    async def exists(self, key: K) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass
    
    @abstractmethod
    async def keys(self, pattern: Optional[str] = None) -> List[K]:
        """Get all keys matching pattern."""
        pass
    
    @abstractmethod
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        pass


class MemoryCache(CacheInterface[str, Any]):
    """In-memory cache implementation with various eviction policies."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []  # For LRU
        self._access_count: Dict[str, int] = {}  # For LFU
        self._stats = CacheStats()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        async with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check TTL
            if entry.expires_at and datetime.now() > entry.expires_at:
                await self._remove_key(key)
                self._stats.misses += 1
                return None
            
            # Update access info
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            self._access_count[key] = self._access_count.get(key, 0) + 1
            
            # Update LRU order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            self._stats.hits += 1
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value with optional TTL."""
        async with self._lock:
            ttl = ttl or self.config.default_ttl
            expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
            
            # Check if we need to evict
            if key not in self._cache and len(self._cache) >= self.config.max_size:
                await self._evict()
            
            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                expires_at=expires_at,
                access_count=1,
                last_accessed=datetime.now()
            )
            
            self._cache[key] = entry
            self._access_count[key] = 1
            
            # Update LRU order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            self._stats.sets += 1
            self._stats.size = len(self._cache)
    
    async def delete(self, key: str) -> bool:
        """Delete key and return True if existed."""
        async with self._lock:
            if key in self._cache:
                await self._remove_key(key)
                self._stats.deletes += 1
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        async with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.expires_at and datetime.now() > entry.expires_at:
                await self._remove_key(key)
                return False
            
            return True
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._access_count.clear()
            self._stats.size = 0
    
    async def keys(self, pattern: Optional[str] = None) -> List[str]:
        """Get all keys matching pattern."""
        async with self._lock:
            if pattern is None:
                return list(self._cache.keys())
            
            import fnmatch
            return [key for key in self._cache.keys() if fnmatch.fnmatch(key, pattern)]
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        self._stats.size = len(self._cache)
        self._stats.memory_usage_bytes = sum(
            len(str(entry.key)) + len(str(entry.value)) 
            for entry in self._cache.values()
        )
        return self._stats
    
    async def _evict(self) -> None:
        """Evict entries based on policy."""
        if not self._cache:
            return
        
        if self.config.policy == CachePolicy.LRU:
            # Remove least recently used
            key_to_remove = self._access_order[0]
        elif self.config.policy == CachePolicy.LFU:
            # Remove least frequently used
            key_to_remove = min(self._access_count.keys(), key=self._access_count.get)
        elif self.config.policy == CachePolicy.FIFO:
            # Remove oldest entry
            key_to_remove = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        else:  # TTL
            # Remove entry with earliest expiration
            key_to_remove = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].expires_at or datetime.max
            )
        
        await self._remove_key(key_to_remove)
        self._stats.evictions += 1
    
    async def _remove_key(self, key: str) -> None:
        """Remove key from all data structures."""
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_count.pop(key, None)
        self._stats.size = len(self._cache)
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries and return count."""
        async with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.expires_at and now > entry.expires_at
            ]
            
            for key in expired_keys:
                await self._remove_key(key)
            
            return len(expired_keys)


class RedisCache(CacheInterface[str, Any]):
    """Redis-based cache implementation."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self._redis: Optional[redis.Redis] = None
        self._stats = CacheStats()
        self._connected = False
    
    async def _ensure_connection(self) -> None:
        """Ensure Redis connection is established."""
        if not REDIS_AVAILABLE:
            raise RuntimeError("Redis is not available. Install redis package.")
        
        if not self._connected:
            try:
                self._redis = redis.from_url(
                    self.config.redis_url or "redis://localhost:6379",
                    db=self.config.redis_db,
                    decode_responses=False  # We handle encoding ourselves
                )
                await self._redis.ping()
                self._connected = True
                logger.info("Redis cache connected successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        if self.config.serialization == "pickle":
            return pickle.dumps(value)
        else:  # json
            return json.dumps(value, default=str).encode('utf-8')
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        if self.config.serialization == "pickle":
            return pickle.loads(data)
        else:  # json
            return json.loads(data.decode('utf-8'))
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key."""
        return f"{self.config.key_prefix}:{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        await self._ensure_connection()
        
        try:
            redis_key = self._make_key(key)
            data = await self._redis.get(redis_key)
            
            if data is None:
                self._stats.misses += 1
                return None
            
            value = self._deserialize(data)
            self._stats.hits += 1
            return value
            
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._stats.misses += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value with optional TTL."""
        await self._ensure_connection()
        
        try:
            redis_key = self._make_key(key)
            data = self._serialize(value)
            ttl = ttl or self.config.default_ttl
            
            if ttl > 0:
                await self._redis.setex(redis_key, ttl, data)
            else:
                await self._redis.set(redis_key, data)
            
            self._stats.sets += 1
            
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            raise
    
    async def delete(self, key: str) -> bool:
        """Delete key and return True if existed."""
        await self._ensure_connection()
        
        try:
            redis_key = self._make_key(key)
            result = await self._redis.delete(redis_key)
            
            if result > 0:
                self._stats.deletes += 1
                return True
            return False
            
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        await self._ensure_connection()
        
        try:
            redis_key = self._make_key(key)
            return bool(await self._redis.exists(redis_key))
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        await self._ensure_connection()
        
        try:
            pattern = f"{self.config.key_prefix}:*"
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            raise
    
    async def keys(self, pattern: Optional[str] = None) -> List[str]:
        """Get all keys matching pattern."""
        await self._ensure_connection()
        
        try:
            redis_pattern = f"{self.config.key_prefix}:{pattern or '*'}"
            redis_keys = await self._redis.keys(redis_pattern)
            
            # Remove prefix from keys
            prefix_len = len(self.config.key_prefix) + 1
            return [key.decode('utf-8')[prefix_len:] for key in redis_keys]
            
        except Exception as e:
            logger.error(f"Redis keys error: {e}")
            return []
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._connected = False


class HybridCache(CacheInterface[str, Any]):
    """Hybrid cache using both memory and Redis."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        
        # Create memory cache for L1
        memory_config = CacheConfig(
            backend=CacheBackend.MEMORY,
            policy=config.policy,
            max_size=min(config.max_size // 4, 1000),  # Smaller L1 cache
            default_ttl=config.default_ttl
        )
        self.l1_cache = MemoryCache(memory_config)
        
        # Create Redis cache for L2
        self.l2_cache = RedisCache(config)
        
        self._stats = CacheStats()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from L1 first, then L2."""
        # Try L1 cache first
        value = await self.l1_cache.get(key)
        if value is not None:
            self._stats.hits += 1
            return value
        
        # Try L2 cache
        value = await self.l2_cache.get(key)
        if value is not None:
            # Promote to L1 cache
            await self.l1_cache.set(key, value)
            self._stats.hits += 1
            return value
        
        self._stats.misses += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in both L1 and L2."""
        await self.l1_cache.set(key, value, ttl)
        await self.l2_cache.set(key, value, ttl)
        self._stats.sets += 1
    
    async def delete(self, key: str) -> bool:
        """Delete from both L1 and L2."""
        l1_deleted = await self.l1_cache.delete(key)
        l2_deleted = await self.l2_cache.delete(key)
        
        if l1_deleted or l2_deleted:
            self._stats.deletes += 1
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in either cache."""
        return await self.l1_cache.exists(key) or await self.l2_cache.exists(key)
    
    async def clear(self) -> None:
        """Clear both caches."""
        await self.l1_cache.clear()
        await self.l2_cache.clear()
    
    async def keys(self, pattern: Optional[str] = None) -> List[str]:
        """Get keys from L2 cache."""
        return await self.l2_cache.keys(pattern)
    
    def get_stats(self) -> CacheStats:
        """Get combined cache statistics."""
        l1_stats = self.l1_cache.get_stats()
        l2_stats = self.l2_cache.get_stats()
        
        return CacheStats(
            hits=self._stats.hits,
            misses=self._stats.misses,
            sets=self._stats.sets,
            deletes=self._stats.deletes,
            evictions=l1_stats.evictions,
            size=l1_stats.size + l2_stats.size,
            memory_usage_bytes=l1_stats.memory_usage_bytes
        )


class CacheManager(metaclass=SingletonMeta):
    """Main cache manager with multiple cache instances."""
    
    def __init__(self):
        self._caches: Dict[str, CacheInterface] = {}
        self._default_config = CacheConfig()
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
    
    def create_cache(self, name: str, config: Optional[CacheConfig] = None) -> CacheInterface:
        """Create a new cache instance."""
        config = config or self._default_config
        
        if config.backend == CacheBackend.MEMORY:
            cache = MemoryCache(config)
        elif config.backend == CacheBackend.REDIS:
            cache = RedisCache(config)
        elif config.backend == CacheBackend.HYBRID:
            cache = HybridCache(config)
        else:
            raise ValueError(f"Unknown cache backend: {config.backend}")
        
        self._caches[name] = cache
        logger.info(f"Created {config.backend.value} cache: {name}")
        
        return cache
    
    def get_cache(self, name: str) -> Optional[CacheInterface]:
        """Get cache instance by name."""
        return self._caches.get(name)
    
    def get_or_create_cache(self, name: str, config: Optional[CacheConfig] = None) -> CacheInterface:
        """Get existing cache or create new one."""
        cache = self.get_cache(name)
        if cache is None:
            cache = self.create_cache(name, config)
        return cache
    
    async def start_monitoring(self, interval: int = 300) -> None:
        """Start cache monitoring."""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop(interval))
        logger.info(f"Cache monitoring started with {interval}s interval")
    
    async def stop_monitoring(self) -> None:
        """Stop cache monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Cache monitoring stopped")
    
    async def _monitoring_loop(self, interval: int) -> None:
        """Cache monitoring loop."""
        while self._is_monitoring:
            try:
                # Cleanup expired entries in memory caches
                for name, cache in self._caches.items():
                    if isinstance(cache, (MemoryCache, HybridCache)):
                        if isinstance(cache, MemoryCache):
                            expired_count = await cache.cleanup_expired()
                        else:  # HybridCache
                            expired_count = await cache.l1_cache.cleanup_expired()
                        
                        if expired_count > 0:
                            logger.debug(f"Cleaned up {expired_count} expired entries from cache {name}")
                
                # Record cache metrics
                for name, cache in self._caches.items():
                    stats = cache.get_stats()
                    performance_monitor.record_metric(
                        name=f"cache_{name}_hit_rate",
                        value=stats.hit_rate,
                        unit="ratio",
                        tags={'cache_name': name}
                    )
                    performance_monitor.record_metric(
                        name=f"cache_{name}_size",
                        value=stats.size,
                        unit="count",
                        tags={'cache_name': name}
                    )
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in cache monitoring loop: {e}")
                await asyncio.sleep(interval)
    
    def get_all_stats(self) -> Dict[str, CacheStats]:
        """Get statistics for all caches."""
        return {name: cache.get_stats() for name, cache in self._caches.items()}
    
    async def clear_all(self) -> None:
        """Clear all caches."""
        for cache in self._caches.values():
            await cache.clear()
        logger.info("All caches cleared")
    
    async def close_all(self) -> None:
        """Close all cache connections."""
        for cache in self._caches.values():
            if hasattr(cache, 'close'):
                await cache.close()
        self._caches.clear()
        logger.info("All cache connections closed")


# Decorators for caching
def cached(
    cache_name: str = "default",
    ttl: Optional[int] = None,
    key_func: Optional[Callable[..., str]] = None
):
    """Decorator to cache function results."""
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            cache_manager = CacheManager()
            cache = cache_manager.get_or_create_cache(cache_name)
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Simple key generation
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we can't use async cache operations
            # This is a simplified version
            return func(*args, **kwargs)
        
        # Return appropriate wrapper
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def cache_invalidate(cache_name: str = "default", pattern: Optional[str] = None):
    """Decorator to invalidate cache after function execution."""
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Invalidate cache
            cache_manager = CacheManager()
            cache = cache_manager.get_cache(cache_name)
            if cache:
                if pattern:
                    keys = await cache.keys(pattern)
                    for key in keys:
                        await cache.delete(key)
                else:
                    await cache.clear()
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Return appropriate wrapper
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Global cache manager instance
cache_manager = CacheManager()

# Pre-configured cache instances
def get_default_cache() -> CacheInterface:
    """Get default cache instance."""
    return cache_manager.get_or_create_cache("default")

def get_api_cache() -> CacheInterface:
    """Get API response cache instance."""
    config = CacheConfig(
        backend=CacheBackend.REDIS if REDIS_AVAILABLE else CacheBackend.MEMORY,
        default_ttl=LONG_CACHE_TTL,
        max_size=5000
    )
    return cache_manager.get_or_create_cache("api_responses", config)

def get_session_cache() -> CacheInterface:
    """Get session cache instance."""
    config = CacheConfig(
        backend=CacheBackend.MEMORY,
        default_ttl=SHORT_CACHE_TTL,
        max_size=1000,
        policy=CachePolicy.LRU
    )
    return cache_manager.get_or_create_cache("sessions", config)