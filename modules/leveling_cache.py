"""
Specialized caching layer for the user leveling system.

This module provides intelligent caching strategies specifically designed
for leveling system data with cache warming, invalidation, and performance optimization.
"""

import logging
import time
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

from modules.caching_system import cache_manager, CacheConfig, CacheBackend
from modules.leveling_models import UserStats, Achievement, UserAchievement
from modules.types import UserId, ChatId
from modules.performance_monitor import performance_monitor

logger = logging.getLogger(__name__)


@dataclass
class CacheMetrics:
    """Cache performance metrics for the leveling system."""
    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    warm_ups: int = 0
    errors: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class LevelingCache:
    """
    Specialized cache for leveling system with intelligent caching strategies.
    
    Features:
    - User stats caching with TTL
    - Achievement definition caching
    - Leaderboard caching
    - Cache warming for active users
    - Intelligent invalidation
    """
    
    def __init__(self):
        """Initialize the leveling cache system."""
        # User stats cache (short TTL for frequently changing data)
        self.user_stats_cache = cache_manager.get_or_create_cache(
            "leveling_user_stats",
            CacheConfig(
                backend=CacheBackend.MEMORY,
                default_ttl=300,  # 5 minutes
                max_size=2000,
                key_prefix="leveling_stats"
            )
        )
        
        # Achievement definitions cache (long TTL for static data)
        self.achievements_cache = cache_manager.get_or_create_cache(
            "leveling_achievements",
            CacheConfig(
                backend=CacheBackend.MEMORY,
                default_ttl=3600,  # 1 hour
                max_size=500,
                key_prefix="leveling_achievements"
            )
        )
        
        # Leaderboard cache (medium TTL for semi-static data)
        self.leaderboard_cache = cache_manager.get_or_create_cache(
            "leveling_leaderboard",
            CacheConfig(
                backend=CacheBackend.MEMORY,
                default_ttl=600,  # 10 minutes
                max_size=100,
                key_prefix="leveling_leaderboard"
            )
        )
        
        # User achievements cache
        self.user_achievements_cache = cache_manager.get_or_create_cache(
            "leveling_user_achievements",
            CacheConfig(
                backend=CacheBackend.MEMORY,
                default_ttl=900,  # 15 minutes
                max_size=1000,
                key_prefix="leveling_user_achievements"
            )
        )
        
        # Cache metrics
        self.metrics = CacheMetrics()
        
        # Active users tracking for cache warming
        self.active_users: Set[tuple[UserId, ChatId]] = set()
        self.last_warm_up = datetime.now()
        self.warm_up_interval = 300  # 5 minutes
    
    # User Stats Caching
    
    async def get_user_stats(self, user_id: UserId, chat_id: ChatId) -> Optional[Dict[str, Any]]:
        """Get cached user stats."""
        cache_key = f"stats:{user_id}:{chat_id}"
        
        try:
            cached_data = await self.user_stats_cache.get(cache_key)
            if cached_data:
                self.metrics.hits += 1
                performance_monitor.record_metric("leveling_cache_hit", 1, tags={"type": "user_stats"})
                return cached_data
            
            self.metrics.misses += 1
            performance_monitor.record_metric("leveling_cache_miss", 1, tags={"type": "user_stats"})
            return None
            
        except Exception as e:
            logger.warning(f"Cache error getting user stats: {e}")
            self.metrics.errors += 1
            return None
    
    async def set_user_stats(self, user_id: UserId, chat_id: ChatId, user_stats: UserStats, ttl: Optional[int] = None) -> None:
        """Cache user stats."""
        cache_key = f"stats:{user_id}:{chat_id}"
        
        try:
            await self.user_stats_cache.set(cache_key, user_stats.to_dict(), ttl)
            
            # Track active user for cache warming
            self.active_users.add((user_id, chat_id))
            
            performance_monitor.record_metric("leveling_cache_set", 1, tags={"type": "user_stats"})
            
        except Exception as e:
            logger.warning(f"Cache error setting user stats: {e}")
            self.metrics.errors += 1
    
    async def invalidate_user_stats(self, user_id: UserId, chat_id: ChatId) -> None:
        """Invalidate cached user stats."""
        cache_key = f"stats:{user_id}:{chat_id}"
        
        try:
            await self.user_stats_cache.delete(cache_key)
            self.metrics.invalidations += 1
            performance_monitor.record_metric("leveling_cache_invalidation", 1, tags={"type": "user_stats"})
            
        except Exception as e:
            logger.warning(f"Cache error invalidating user stats: {e}")
            self.metrics.errors += 1
    
    # Achievement Caching
    
    async def get_achievements(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached achievement definitions."""
        cache_key = "all_achievements"
        
        try:
            cached_data = await self.achievements_cache.get(cache_key)
            if cached_data:
                self.metrics.hits += 1
                performance_monitor.record_metric("leveling_cache_hit", 1, tags={"type": "achievements"})
                return cached_data
            
            self.metrics.misses += 1
            performance_monitor.record_metric("leveling_cache_miss", 1, tags={"type": "achievements"})
            return None
            
        except Exception as e:
            logger.warning(f"Cache error getting achievements: {e}")
            self.metrics.errors += 1
            return None
    
    async def set_achievements(self, achievements: List[Achievement], ttl: Optional[int] = None) -> None:
        """Cache achievement definitions."""
        cache_key = "all_achievements"
        
        try:
            achievement_dicts = [ach.to_dict() for ach in achievements]
            await self.achievements_cache.set(cache_key, achievement_dicts, ttl)
            performance_monitor.record_metric("leveling_cache_set", 1, tags={"type": "achievements"})
            
        except Exception as e:
            logger.warning(f"Cache error setting achievements: {e}")
            self.metrics.errors += 1
    
    async def invalidate_achievements(self) -> None:
        """Invalidate cached achievements."""
        try:
            await self.achievements_cache.clear()
            self.metrics.invalidations += 1
            performance_monitor.record_metric("leveling_cache_invalidation", 1, tags={"type": "achievements"})
            
        except Exception as e:
            logger.warning(f"Cache error invalidating achievements: {e}")
            self.metrics.errors += 1
    
    # User Achievements Caching
    
    async def get_user_achievements(self, user_id: UserId, chat_id: ChatId) -> Optional[List[Dict[str, Any]]]:
        """Get cached user achievements."""
        cache_key = f"user_achievements:{user_id}:{chat_id}"
        
        try:
            cached_data = await self.user_achievements_cache.get(cache_key)
            if cached_data:
                self.metrics.hits += 1
                performance_monitor.record_metric("leveling_cache_hit", 1, tags={"type": "user_achievements"})
                return cached_data
            
            self.metrics.misses += 1
            performance_monitor.record_metric("leveling_cache_miss", 1, tags={"type": "user_achievements"})
            return None
            
        except Exception as e:
            logger.warning(f"Cache error getting user achievements: {e}")
            self.metrics.errors += 1
            return None
    
    async def set_user_achievements(self, user_id: UserId, chat_id: ChatId, achievements: List[Achievement], ttl: Optional[int] = None) -> None:
        """Cache user achievements."""
        cache_key = f"user_achievements:{user_id}:{chat_id}"
        
        try:
            achievement_dicts = [ach.to_dict() for ach in achievements]
            await self.user_achievements_cache.set(cache_key, achievement_dicts, ttl)
            performance_monitor.record_metric("leveling_cache_set", 1, tags={"type": "user_achievements"})
            
        except Exception as e:
            logger.warning(f"Cache error setting user achievements: {e}")
            self.metrics.errors += 1
    
    async def invalidate_user_achievements(self, user_id: UserId, chat_id: ChatId) -> None:
        """Invalidate cached user achievements."""
        cache_key = f"user_achievements:{user_id}:{chat_id}"
        
        try:
            await self.user_achievements_cache.delete(cache_key)
            self.metrics.invalidations += 1
            performance_monitor.record_metric("leveling_cache_invalidation", 1, tags={"type": "user_achievements"})
            
        except Exception as e:
            logger.warning(f"Cache error invalidating user achievements: {e}")
            self.metrics.errors += 1
    
    # Leaderboard Caching
    
    async def get_leaderboard(self, chat_id: ChatId, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Get cached leaderboard."""
        cache_key = f"leaderboard:{chat_id}:{limit}"
        
        try:
            cached_data = await self.leaderboard_cache.get(cache_key)
            if cached_data:
                self.metrics.hits += 1
                performance_monitor.record_metric("leveling_cache_hit", 1, tags={"type": "leaderboard"})
                return cached_data
            
            self.metrics.misses += 1
            performance_monitor.record_metric("leveling_cache_miss", 1, tags={"type": "leaderboard"})
            return None
            
        except Exception as e:
            logger.warning(f"Cache error getting leaderboard: {e}")
            self.metrics.errors += 1
            return None
    
    async def set_leaderboard(self, chat_id: ChatId, limit: int, leaderboard_data: List[Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """Cache leaderboard data."""
        cache_key = f"leaderboard:{chat_id}:{limit}"
        
        try:
            await self.leaderboard_cache.set(cache_key, leaderboard_data, ttl)
            performance_monitor.record_metric("leveling_cache_set", 1, tags={"type": "leaderboard"})
            
        except Exception as e:
            logger.warning(f"Cache error setting leaderboard: {e}")
            self.metrics.errors += 1
    
    async def invalidate_leaderboard(self, chat_id: ChatId) -> None:
        """Invalidate cached leaderboard for a chat."""
        try:
            # Invalidate all leaderboard entries for this chat
            pattern = f"leaderboard:{chat_id}:*"
            keys = await self.leaderboard_cache.keys(pattern)
            
            for key in keys:
                await self.leaderboard_cache.delete(key)
            
            self.metrics.invalidations += len(keys)
            performance_monitor.record_metric("leveling_cache_invalidation", len(keys), tags={"type": "leaderboard"})
            
        except Exception as e:
            logger.warning(f"Cache error invalidating leaderboard: {e}")
            self.metrics.errors += 1
    
    # Cache Warming and Optimization
    
    async def warm_up_cache(self, user_stats_loader, achievements_loader) -> None:
        """Warm up cache with frequently accessed data."""
        if (datetime.now() - self.last_warm_up).total_seconds() < self.warm_up_interval:
            return
        
        try:
            # Warm up achievement definitions if not cached
            if not await self.get_achievements():
                achievements = await achievements_loader()
                if achievements:
                    await self.set_achievements(achievements)
                    self.metrics.warm_ups += 1
            
            # Warm up active user stats
            for user_id, chat_id in list(self.active_users)[-50:]:  # Limit to most recent 50 active users
                if not await self.get_user_stats(user_id, chat_id):
                    try:
                        user_stats = await user_stats_loader(user_id, chat_id)
                        if user_stats:
                            await self.set_user_stats(user_id, chat_id, user_stats)
                            self.metrics.warm_ups += 1
                    except Exception as e:
                        logger.debug(f"Failed to warm up cache for user {user_id}: {e}")
            
            self.last_warm_up = datetime.now()
            performance_monitor.record_metric("leveling_cache_warmup", 1)
            
        except Exception as e:
            logger.warning(f"Cache warm-up error: {e}")
            self.metrics.errors += 1
    
    async def invalidate_user_related_caches(self, user_id: UserId, chat_id: ChatId) -> None:
        """Invalidate all caches related to a user (when they level up or get achievements)."""
        try:
            # Invalidate user stats
            await self.invalidate_user_stats(user_id, chat_id)
            
            # Invalidate user achievements
            await self.invalidate_user_achievements(user_id, chat_id)
            
            # Invalidate leaderboard for the chat (since user's position might have changed)
            await self.invalidate_leaderboard(chat_id)
            
            performance_monitor.record_metric("leveling_cache_user_invalidation", 1)
            
        except Exception as e:
            logger.warning(f"Error invalidating user-related caches: {e}")
            self.metrics.errors += 1
    
    def get_cache_metrics(self) -> Dict[str, Any]:
        """Get comprehensive cache metrics."""
        return {
            'metrics': {
                'hits': self.metrics.hits,
                'misses': self.metrics.misses,
                'hit_rate': self.metrics.hit_rate,
                'invalidations': self.metrics.invalidations,
                'warm_ups': self.metrics.warm_ups,
                'errors': self.metrics.errors
            },
            'cache_stats': {
                'user_stats': self.user_stats_cache.get_stats().__dict__,
                'achievements': self.achievements_cache.get_stats().__dict__,
                'leaderboard': self.leaderboard_cache.get_stats().__dict__,
                'user_achievements': self.user_achievements_cache.get_stats().__dict__
            },
            'active_users_count': len(self.active_users),
            'last_warm_up': self.last_warm_up.isoformat()
        }
    
    async def clear_all_caches(self) -> None:
        """Clear all leveling-related caches."""
        try:
            await self.user_stats_cache.clear()
            await self.achievements_cache.clear()
            await self.leaderboard_cache.clear()
            await self.user_achievements_cache.clear()
            
            self.active_users.clear()
            self.metrics = CacheMetrics()
            
            logger.info("All leveling caches cleared")
            
        except Exception as e:
            logger.error(f"Error clearing caches: {e}")
            self.metrics.errors += 1


# Global leveling cache instance
leveling_cache = LevelingCache()