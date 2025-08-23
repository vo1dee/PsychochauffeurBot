"""
Repository layer for the user leveling system.

This module provides database access layer for user statistics and achievements,
implementing CRUD operations with transaction support and error handling.
"""

import logging
import time
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import asyncpg
import pytz

from modules.database import Database
from modules.leveling_models import UserStats, Achievement, UserAchievement, UserProfile
from modules.types import UserId, ChatId
from modules.error_decorators import database_operation
from modules.service_error_boundary import with_error_boundary
from modules.performance_monitor import performance_monitor
from modules.leveling_performance_monitor import record_database_time

logger = logging.getLogger(__name__)


class UserStatsRepository:
    """
    Repository for user statistics database operations.
    
    Provides CRUD operations for user statistics with transaction support
    and optimized queries for performance.
    """
    
    def __init__(self):
        self._connection_manager = Database.get_connection_manager()
    
    @database_operation("get_user_stats", retry_count=3)
    @with_error_boundary("user_stats_repository", "get_user_stats", timeout=5.0)
    async def get_user_stats(self, user_id: UserId, chat_id: ChatId) -> Optional[UserStats]:
        """
        Get user statistics for a specific user in a specific chat.
        Enhanced with retry mechanisms and performance monitoring.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            
        Returns:
            UserStats object if found, None otherwise
        """
        start_time = time.time()
        
        try:
            async with self._connection_manager.get_connection() as conn:
                row = await conn.fetchrow("""
                    SELECT user_id, chat_id, xp, level, messages_count, links_shared, 
                           thanks_received, last_activity, created_at, updated_at
                    FROM user_chat_stats
                    WHERE user_id = $1 AND chat_id = $2
                """, user_id, chat_id)
                
                # Record performance metrics
                query_time = time.time() - start_time
                performance_monitor.record_metric(
                    "db_query_user_stats_time", 
                    query_time, 
                    "seconds",
                    {"operation": "get_user_stats"}
                )
                record_database_time("get_user_stats", query_time)
                
                if row:
                    return UserStats.from_dict(dict(row))
                return None
                
        except Exception as e:
            # Record error metrics
            performance_monitor.record_metric("db_query_user_stats_errors", 1)
            logger.error(f"Database error in get_user_stats: {e}")
            raise
    
    @database_operation("create_user_stats")
    async def create_user_stats(self, user_id: UserId, chat_id: ChatId) -> UserStats:
        """
        Create new user statistics record.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            
        Returns:
            Newly created UserStats object
        """
        now = datetime.now(pytz.utc)
        user_stats = UserStats(
            user_id=user_id,
            chat_id=chat_id,
            xp=0,
            level=1,
            messages_count=0,
            links_shared=0,
            thanks_received=0,
            last_activity=now,
            created_at=now,
            updated_at=now
        )
        
        async with self._connection_manager.get_connection() as conn:
            await conn.execute("""
                INSERT INTO user_chat_stats (
                    user_id, chat_id, xp, level, messages_count, links_shared,
                    thanks_received, last_activity, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (user_id, chat_id) DO NOTHING
            """, 
                user_stats.user_id, user_stats.chat_id, user_stats.xp, user_stats.level,
                user_stats.messages_count, user_stats.links_shared, user_stats.thanks_received,
                user_stats.last_activity, user_stats.created_at, user_stats.updated_at
            )
            
            logger.debug(f"Created user stats for user_id={user_id}, chat_id={chat_id}")
            return user_stats
    
    @database_operation("update_user_stats", retry_count=3, raise_exception=True)
    @with_error_boundary("user_stats_repository", "update_user_stats", timeout=10.0)
    async def update_user_stats(self, user_stats: UserStats) -> None:
        """
        Update existing user statistics with enhanced error handling and transaction safety.
        
        Args:
            user_stats: UserStats object with updated values
        """
        user_stats.updated_at = datetime.now(pytz.utc)
        start_time = time.time()
        
        try:
            async with self._connection_manager.get_connection() as conn:
                async with conn.transaction():
                    # Use atomic transaction for consistency
                    result = await conn.execute("""
                        UPDATE user_chat_stats
                        SET xp = $3, level = $4, messages_count = $5, links_shared = $6,
                            thanks_received = $7, last_activity = $8, updated_at = $9
                        WHERE user_id = $1 AND chat_id = $2
                    """,
                        user_stats.user_id, user_stats.chat_id, user_stats.xp, user_stats.level,
                        user_stats.messages_count, user_stats.links_shared, user_stats.thanks_received,
                        user_stats.last_activity, user_stats.updated_at
                    )
                    
                    # Verify the update was successful
                    if result == "UPDATE 0":
                        logger.warning(f"No rows updated for user_id={user_stats.user_id}, chat_id={user_stats.chat_id}")
                        performance_monitor.record_metric("db_update_user_stats_no_rows", 1)
            
            # Record performance metrics
            update_time = time.time() - start_time
            performance_monitor.record_metric(
                "db_update_user_stats_time", 
                update_time, 
                "seconds",
                {"operation": "update_user_stats"}
            )
            record_database_time("update_user_stats", update_time)
            
            logger.debug(f"Updated user stats for user_id={user_stats.user_id}, chat_id={user_stats.chat_id}")
            
        except Exception as e:
            # Record error metrics
            performance_monitor.record_metric("db_update_user_stats_errors", 1)
            logger.error(f"Database error in update_user_stats: {e}")
            raise
    
    @database_operation("get_or_create_user_stats")
    async def get_or_create_user_stats(self, user_id: UserId, chat_id: ChatId) -> UserStats:
        """
        Get user statistics or create if not exists.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            
        Returns:
            UserStats object (existing or newly created)
        """
        user_stats = await self.get_user_stats(user_id, chat_id)
        if user_stats is None:
            user_stats = await self.create_user_stats(user_id, chat_id)
        return user_stats
    
    @database_operation("get_leaderboard")
    async def get_leaderboard(self, chat_id: ChatId, limit: int = 10) -> List[UserStats]:
        """
        Get leaderboard for a chat ordered by XP.
        
        Args:
            chat_id: The chat's ID
            limit: Maximum number of users to return
            
        Returns:
            List of UserStats objects ordered by XP (descending)
        """
        async with self._connection_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT user_id, chat_id, xp, level, messages_count, links_shared,
                       thanks_received, last_activity, created_at, updated_at
                FROM user_chat_stats
                WHERE chat_id = $1
                ORDER BY xp DESC, level DESC, messages_count DESC
                LIMIT $2
            """, chat_id, limit)
            
            return [UserStats.from_dict(dict(row)) for row in rows]
    
    @database_operation("get_user_rank")
    async def get_user_rank(self, user_id: UserId, chat_id: ChatId) -> Optional[int]:
        """
        Get user's rank in the chat leaderboard.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            
        Returns:
            User's rank (1-based) or None if user not found
        """
        async with self._connection_manager.get_connection() as conn:
            row = await conn.fetchrow("""
                WITH ranked_users AS (
                    SELECT user_id, 
                           ROW_NUMBER() OVER (ORDER BY xp DESC, level DESC, messages_count DESC) as rank
                    FROM user_chat_stats
                    WHERE chat_id = $1
                )
                SELECT rank FROM ranked_users WHERE user_id = $2
            """, chat_id, user_id)
            
            return row['rank'] if row else None
    
    @database_operation("get_active_users")
    async def get_active_users(self, chat_id: ChatId, days: int = 7) -> List[UserStats]:
        """
        Get users active within the specified number of days.
        
        Args:
            chat_id: The chat's ID
            days: Number of days to look back for activity
            
        Returns:
            List of UserStats objects for active users
        """
        cutoff_date = datetime.now(pytz.utc) - timedelta(days=days)
        
        async with self._connection_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT user_id, chat_id, xp, level, messages_count, links_shared,
                       thanks_received, last_activity, created_at, updated_at
                FROM user_chat_stats
                WHERE chat_id = $1 AND last_activity >= $2
                ORDER BY last_activity DESC
            """, chat_id, cutoff_date)
            
            return [UserStats.from_dict(dict(row)) for row in rows]
    
    @database_operation("bulk_update_user_stats")
    async def bulk_update_user_stats(self, user_stats_list: List[UserStats]) -> None:
        """
        Update multiple user statistics in a single transaction.
        
        Args:
            user_stats_list: List of UserStats objects to update
        """
        if not user_stats_list:
            return
        
        async with self._connection_manager.get_connection() as conn:
            async with conn.transaction():
                for user_stats in user_stats_list:
                    user_stats.updated_at = datetime.now(pytz.utc)
                    await conn.execute("""
                        UPDATE user_chat_stats
                        SET xp = $3, level = $4, messages_count = $5, links_shared = $6,
                            thanks_received = $7, last_activity = $8, updated_at = $9
                        WHERE user_id = $1 AND chat_id = $2
                    """,
                        user_stats.user_id, user_stats.chat_id, user_stats.xp, user_stats.level,
                        user_stats.messages_count, user_stats.links_shared, user_stats.thanks_received,
                        user_stats.last_activity, user_stats.updated_at
                    )
                
                logger.debug(f"Bulk updated {len(user_stats_list)} user stats records")
    
    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for database transactions.
        
        Usage:
            async with repository.transaction() as conn:
                # Perform multiple operations
                await conn.execute(...)
        """
        async with self._connection_manager.get_connection() as conn:
            async with conn.transaction():
                yield conn


class AchievementRepository:
    """
    Repository for achievement database operations.
    
    Provides CRUD operations for achievements and user achievements
    with transaction support and optimized queries.
    """
    
    def __init__(self):
        self._connection_manager = Database.get_connection_manager()
    
    @database_operation("get_achievement")
    async def get_achievement(self, achievement_id: str) -> Optional[Achievement]:
        """
        Get achievement definition by ID.
        
        Args:
            achievement_id: The achievement's ID
            
        Returns:
            Achievement object if found, None otherwise
        """
        try:
            async with self._connection_manager.get_connection() as conn:
                row = await conn.fetchrow("""
                    SELECT id, title, description, emoji, condition_type, condition_value, category, created_at
                    FROM achievements
                    WHERE id = $1
                """, achievement_id)
                
                if row:
                    return Achievement.from_dict(dict(row))
                return None
        except Exception as e:
            logger.error(f"Error getting achievement {achievement_id}: {e}")
            return None
    
    @database_operation("get_all_achievements")
    async def get_all_achievements(self) -> List[Achievement]:
        """
        Get all achievement definitions.
        
        Returns:
            List of all Achievement objects
        """
        try:
            async with self._connection_manager.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT id, title, description, emoji, condition_type, condition_value, category, created_at
                    FROM achievements
                    ORDER BY category, condition_value
                """)
                
                return [Achievement.from_dict(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error getting all achievements: {e}")
            return []
    
    @database_operation("get_achievements_by_category")
    async def get_achievements_by_category(self, category: str) -> List[Achievement]:
        """
        Get achievements by category.
        
        Args:
            category: The achievement category
            
        Returns:
            List of Achievement objects in the specified category
        """
        try:
            async with self._connection_manager.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT id, title, description, emoji, condition_type, condition_value, category, created_at
                    FROM achievements
                    WHERE category = $1
                    ORDER BY condition_value
                """, category)
                
                return [Achievement.from_dict(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error getting achievements by category {category}: {e}")
            return []
    
    @database_operation("save_achievement")
    async def save_achievement(self, achievement: Achievement) -> None:
        """
        Save or update achievement definition.
        
        Args:
            achievement: Achievement object to save
        """
        async with self._connection_manager.get_connection() as conn:
            await conn.execute("""
                INSERT INTO achievements (id, title, description, emoji, condition_type, condition_value, category, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    emoji = EXCLUDED.emoji,
                    condition_type = EXCLUDED.condition_type,
                    condition_value = EXCLUDED.condition_value,
                    category = EXCLUDED.category
            """,
                achievement.id, achievement.title, achievement.description, achievement.emoji,
                achievement.condition_type, achievement.condition_value, achievement.category,
                achievement.created_at
            )
            
            logger.debug(f"Saved achievement: {achievement.id}")
    
    @database_operation("get_user_achievements")
    async def get_user_achievements(self, user_id: UserId, chat_id: ChatId) -> List[UserAchievement]:
        """
        Get all achievements unlocked by a user in a specific chat.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            
        Returns:
            List of UserAchievement objects
        """
        async with self._connection_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT user_id, chat_id, achievement_id, unlocked_at
                FROM user_achievements
                WHERE user_id = $1 AND chat_id = $2
                ORDER BY unlocked_at DESC
            """, user_id, chat_id)
            
            return [UserAchievement.from_dict(dict(row)) for row in rows]
    
    @database_operation("get_user_achievements_with_details")
    async def get_user_achievements_with_details(self, user_id: UserId, chat_id: ChatId) -> List[Tuple[UserAchievement, Achievement]]:
        """
        Get user achievements with full achievement details.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            
        Returns:
            List of tuples containing (UserAchievement, Achievement)
        """
        async with self._connection_manager.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT ua.user_id, ua.chat_id, ua.achievement_id, ua.unlocked_at,
                       a.title, a.description, a.emoji, a.condition_type, a.condition_value, a.category, a.created_at
                FROM user_achievements ua
                JOIN achievements a ON ua.achievement_id = a.id
                WHERE ua.user_id = $1 AND ua.chat_id = $2
                ORDER BY ua.unlocked_at DESC
            """, user_id, chat_id)
            
            result = []
            for row in rows:
                user_achievement = UserAchievement(
                    user_id=row['user_id'],
                    chat_id=row['chat_id'],
                    achievement_id=row['achievement_id'],
                    unlocked_at=row['unlocked_at']
                )
                achievement = Achievement(
                    id=row['achievement_id'],
                    title=row['title'],
                    description=row['description'],
                    emoji=row['emoji'],
                    sticker=row['emoji'],  # Use emoji as sticker
                    condition_type=row['condition_type'],
                    condition_value=row['condition_value'],
                    category=row['category'],
                    created_at=row['created_at']
                )
                result.append((user_achievement, achievement))
            
            return result
    
    @database_operation("has_achievement")
    async def has_achievement(self, user_id: UserId, chat_id: ChatId, achievement_id: str) -> bool:
        """
        Check if user has unlocked a specific achievement.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            achievement_id: The achievement's ID
            
        Returns:
            True if user has the achievement, False otherwise
        """
        try:
            async with self._connection_manager.get_connection() as conn:
                row = await conn.fetchrow("""
                    SELECT 1 FROM user_achievements
                    WHERE user_id = $1 AND chat_id = $2 AND achievement_id = $3
                """, user_id, chat_id, achievement_id)
                
                return row is not None
        except Exception as e:
            logger.error(f"Error checking achievement {achievement_id} for user {user_id}: {e}")
            return False
    
    @database_operation("unlock_achievement", retry_count=3)
    @with_error_boundary("achievement_repository", "unlock_achievement", timeout=5.0)
    async def unlock_achievement(self, user_achievement: UserAchievement) -> None:
        """
        Unlock an achievement for a user with enhanced error handling.
        
        Args:
            user_achievement: UserAchievement object to save
        """
        start_time = time.time()
        
        try:
            async with self._connection_manager.get_connection() as conn:
                async with conn.transaction():
                    result = await conn.execute("""
                        INSERT INTO user_achievements (user_id, chat_id, achievement_id, unlocked_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (user_id, chat_id, achievement_id) DO NOTHING
                    """,
                        user_achievement.user_id, user_achievement.chat_id,
                        user_achievement.achievement_id, user_achievement.unlocked_at
                    )
                    
                    # Check if achievement was actually inserted (not a duplicate)
                    if "INSERT 0 1" in result:
                        performance_monitor.record_metric("achievement_unlocked", 1)
                    else:
                        performance_monitor.record_metric("achievement_duplicate_attempt", 1)
            
            # Record performance metrics
            unlock_time = time.time() - start_time
            performance_monitor.record_metric(
                "db_unlock_achievement_time", 
                unlock_time, 
                "seconds",
                {"achievement_id": user_achievement.achievement_id}
            )
            record_database_time("unlock_achievement", unlock_time)
            
            logger.debug(f"Unlocked achievement {user_achievement.achievement_id} for user_id={user_achievement.user_id}, chat_id={user_achievement.chat_id}")
            
        except Exception as e:
            # Record error metrics
            performance_monitor.record_metric("db_unlock_achievement_errors", 1)
            logger.error(f"Database error in unlock_achievement: {e}")
            raise
    
    @database_operation("bulk_unlock_achievements")
    async def bulk_unlock_achievements(self, user_achievements: List[UserAchievement]) -> None:
        """
        Unlock multiple achievements in a single transaction.
        
        Args:
            user_achievements: List of UserAchievement objects to unlock
        """
        if not user_achievements:
            return
        
        async with self._connection_manager.get_connection() as conn:
            async with conn.transaction():
                for user_achievement in user_achievements:
                    await conn.execute("""
                        INSERT INTO user_achievements (user_id, chat_id, achievement_id, unlocked_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (user_id, chat_id, achievement_id) DO NOTHING
                    """,
                        user_achievement.user_id, user_achievement.chat_id,
                        user_achievement.achievement_id, user_achievement.unlocked_at
                    )
                
                logger.debug(f"Bulk unlocked {len(user_achievements)} achievements")
    
    @database_operation("get_achievement_stats")
    async def get_achievement_stats(self, chat_id: ChatId) -> Dict[str, int]:
        """
        Get achievement statistics for a chat.
        
        Args:
            chat_id: The chat's ID
            
        Returns:
            Dictionary with achievement statistics
        """
        try:
            async with self._connection_manager.get_connection() as conn:
                # Get total achievements available
                total_achievements = await conn.fetchval("""
                    SELECT COUNT(*) FROM achievements
                """)
                
                # Get achievements unlocked in this chat
                unlocked_achievements = await conn.fetchval("""
                    SELECT COUNT(DISTINCT achievement_id) FROM user_achievements
                    WHERE chat_id = $1
                """, chat_id)
                
                # Get users with achievements
                users_with_achievements = await conn.fetchval("""
                    SELECT COUNT(DISTINCT user_id) FROM user_achievements
                    WHERE chat_id = $1
                """, chat_id)
                
                # Get most popular achievement
                popular_achievement = await conn.fetchrow("""
                    SELECT achievement_id, COUNT(*) as unlock_count
                    FROM user_achievements
                    WHERE chat_id = $1
                    GROUP BY achievement_id
                    ORDER BY unlock_count DESC
                    LIMIT 1
                """, chat_id)
                
                return {
                    'total_achievements': total_achievements or 0,
                    'unlocked_achievements': unlocked_achievements or 0,
                    'users_with_achievements': users_with_achievements or 0,
                    'most_popular_achievement': popular_achievement['achievement_id'] if popular_achievement else None,
                    'most_popular_count': popular_achievement['unlock_count'] if popular_achievement else 0
                }
        except Exception as e:
            logger.error(f"Error getting achievement stats for chat {chat_id}: {e}")
            return {
                'total_achievements': 0,
                'unlocked_achievements': 0,
                'users_with_achievements': 0,
                'most_popular_achievement': None,
                'most_popular_count': 0
            }
    
    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for database transactions.
        
        Usage:
            async with repository.transaction() as conn:
                # Perform multiple operations
                await conn.execute(...)
        """
        async with self._connection_manager.get_connection() as conn:
            async with conn.transaction():
                yield conn


class LevelingRepository:
    """
    Combined repository for leveling system operations.
    
    Provides high-level operations that combine user stats and achievements
    with atomic transaction support.
    """
    
    def __init__(self):
        self.user_stats = UserStatsRepository()
        self.achievements = AchievementRepository()
        self._connection_manager = Database.get_connection_manager()
    
    @database_operation("update_user_xp_atomic")
    async def update_user_xp_atomic(
        self,
        user_id: UserId,
        chat_id: ChatId,
        xp_gain: int,
        new_level: int,
        activity_updates: Dict[str, int],
        new_achievements: List[UserAchievement]
    ) -> UserStats:
        """
        Atomically update user XP, level, activity counters, and unlock achievements.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            xp_gain: Amount of XP to add
            new_level: New level for the user
            activity_updates: Dictionary of activity counters to update
            new_achievements: List of new achievements to unlock
            
        Returns:
            Updated UserStats object
        """
        async with self._connection_manager.get_connection() as conn:
            async with conn.transaction():
                # Get or create user stats
                user_stats = await self.user_stats.get_or_create_user_stats(user_id, chat_id)
                
                # Update user stats
                user_stats.add_xp(xp_gain)
                user_stats.update_level(new_level)
                
                # Apply activity updates
                for activity, increment in activity_updates.items():
                    if activity == 'messages_count':
                        user_stats.messages_count += increment
                    elif activity == 'links_shared':
                        user_stats.links_shared += increment
                    elif activity == 'thanks_received':
                        user_stats.thanks_received += increment
                
                # Update in database
                await conn.execute("""
                    UPDATE user_chat_stats
                    SET xp = $3, level = $4, messages_count = $5, links_shared = $6,
                        thanks_received = $7, last_activity = $8, updated_at = $9
                    WHERE user_id = $1 AND chat_id = $2
                """,
                    user_stats.user_id, user_stats.chat_id, user_stats.xp, user_stats.level,
                    user_stats.messages_count, user_stats.links_shared, user_stats.thanks_received,
                    user_stats.last_activity, user_stats.updated_at
                )
                
                # Unlock new achievements
                for user_achievement in new_achievements:
                    await conn.execute("""
                        INSERT INTO user_achievements (user_id, chat_id, achievement_id, unlocked_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (user_id, chat_id, achievement_id) DO NOTHING
                    """,
                        user_achievement.user_id, user_achievement.chat_id,
                        user_achievement.achievement_id, user_achievement.unlocked_at
                    )
                
                logger.debug(f"Atomically updated user {user_id} in chat {chat_id}: +{xp_gain} XP, level {new_level}, {len(new_achievements)} new achievements")
                return user_stats
    
    @database_operation("get_user_profile")
    async def get_user_profile(self, user_id: UserId, chat_id: ChatId, username: Optional[str] = None) -> Optional[UserProfile]:
        """
        Get complete user profile with stats, achievements, and rank.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            username: Optional username for display
            
        Returns:
            UserProfile object if user exists, None otherwise
        """
        user_stats = await self.user_stats.get_user_stats(user_id, chat_id)
        if not user_stats:
            return None
        
        # Get user achievements with details
        achievement_data = await self.achievements.get_user_achievements_with_details(user_id, chat_id)
        achievements = [achievement for _, achievement in achievement_data]
        
        # Get user rank
        rank = await self.user_stats.get_user_rank(user_id, chat_id)
        
        # Calculate next level progress (this would typically use LevelManager)
        # For now, using a simple calculation
        next_level_xp = user_stats.level * 100  # Simplified calculation
        progress_percentage = min(100.0, (user_stats.xp / next_level_xp) * 100)
        
        return UserProfile.from_user_stats(
            user_stats=user_stats,
            username=username,
            next_level_xp=next_level_xp,
            progress_percentage=progress_percentage,
            achievements=achievements,
            rank=rank
        )
    
    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for database transactions across all repositories.
        
        Usage:
            async with repository.transaction() as conn:
                # Perform multiple operations across repositories
                await conn.execute(...)
        """
        async with self._connection_manager.get_connection() as conn:
            async with conn.transaction():
                yield conn