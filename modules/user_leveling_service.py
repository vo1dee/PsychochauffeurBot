"""
User Leveling Service for the Telegram bot.

This service orchestrates the entire leveling system, integrating XP calculation,
level management, achievement checking, and notifications.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import asyncio
import time

from telegram import Update, Message
from telegram.ext import ContextTypes

from modules.service_registry import ServiceInterface
from modules.xp_calculator import XPCalculator
from modules.level_manager import LevelManager
from modules.achievement_engine import AchievementEngine
from modules.repositories import UserStatsRepository, AchievementRepository
from modules.leveling_models import UserStats, UserProfile, LevelUpResult
from modules.leveling_notification_service import LevelingNotificationService
from modules.types import UserId, ChatId
from modules.error_decorators import database_operation
from modules.service_error_boundary import ServiceErrorBoundary

logger = logging.getLogger(__name__)


class UserLevelingService(ServiceInterface):
    """
    Main service orchestrating the user leveling system.
    
    This service handles:
    - Message processing for XP calculation
    - Level progression tracking
    - Achievement unlocking
    - User profile management
    - Integration with the bot's message pipeline
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize the UserLevelingService.
        
        Args:
            config_manager: Configuration manager for system settings
        """
        self.config_manager = config_manager
        self._initialized = False
        
        # Core components
        self.xp_calculator: Optional[XPCalculator] = None
        self.level_manager: Optional[LevelManager] = None
        self.achievement_engine: Optional[AchievementEngine] = None
        
        # Repositories
        self.user_stats_repo: Optional[UserStatsRepository] = None
        self.achievement_repo: Optional[AchievementRepository] = None
        
        # Notification service
        self.notification_service: Optional[LevelingNotificationService] = None
        
        # Service configuration
        self._service_config: Dict[str, Any] = {}
        self._enabled = True
        
        # Error handling
        self.error_boundary = ServiceErrorBoundary("user_leveling_service")
        
        # Performance tracking
        self._stats = {
            'messages_processed': 0,
            'xp_awarded': 0,
            'levels_gained': 0,
            'achievements_unlocked': 0,
            'errors': 0,
            'rate_limited': 0,
            'processing_time_total': 0.0,
            'processing_time_avg': 0.0
        }
        
        # Rate limiting
        self._user_xp_timestamps: Dict[int, List[float]] = {}
        self._rate_limit_window = 60  # 1 minute window
        self._max_xp_per_window = 10  # Max XP per user per minute
        
        # Performance monitoring
        self._processing_times: List[float] = []
        self._max_processing_time = 0.1  # 100ms max processing time
        
        logger.info("UserLevelingService instance created")
    
    async def initialize(self) -> None:
        """Initialize the leveling service with all components."""
        if self._initialized:
            logger.debug("UserLevelingService already initialized, skipping")
            return
        
        logger.info("Initializing UserLevelingService...")
        
        try:
            # Load service configuration
            await self._load_service_configuration()
            
            # Initialize core components
            self.xp_calculator = XPCalculator()
            self.level_manager = LevelManager(
                base_xp=self._service_config.get('level_base_xp', 50),
                multiplier=self._service_config.get('level_multiplier', 2.0)
            )
            
            # Initialize repositories
            self.user_stats_repo = UserStatsRepository()
            self.achievement_repo = AchievementRepository()
            
            # Initialize achievement engine with repository
            self.achievement_engine = AchievementEngine(self.achievement_repo)
            
            # Initialize notification service
            notification_config = self._service_config.get('notifications', {})
            self.notification_service = LevelingNotificationService(notification_config)
            
            # Initialize achievement definitions in database
            await self.achievement_engine.initialize_achievement_definitions()
            
            # Perform initial retroactive checks if enabled
            if self._service_config.get('perform_startup_retroactive_checks', False):
                logger.info("Performing startup retroactive checks...")
                # This is optional and can be enabled via configuration
                # It will check existing users' stats and update levels/achievements
                # Note: This is commented out by default to avoid startup delays
                # await self._perform_startup_retroactive_checks()
            
            self._initialized = True
            logger.info("UserLevelingService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize UserLevelingService: {e}", exc_info=True)
            self._stats['errors'] += 1
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the leveling service and cleanup resources."""
        logger.info("Shutting down UserLevelingService...")
        
        try:
            # Log final statistics
            logger.info(f"UserLevelingService statistics: {self._stats}")
            
            # Cleanup components
            self.xp_calculator = None
            self.level_manager = None
            self.achievement_engine = None
            self.user_stats_repo = None
            self.achievement_repo = None
            self.notification_service = None
            
            self._initialized = False
            logger.info("UserLevelingService shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during UserLevelingService shutdown: {e}", exc_info=True)
    
    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Process a message for XP calculation and leveling updates.
        
        This is the main entry point for message processing integration.
        Enhanced with performance safeguards and retroactive checking.
        
        Args:
            update: Telegram update containing the message
            context: Bot context
        """
        if not self._initialized or not self._enabled:
            return
        
        # Validate message
        if not update.message or not update.message.from_user:
            return
        
        # Skip bot messages
        if update.message.from_user.is_bot:
            return
        
        # Skip private chats (leveling is for groups only)
        if update.effective_chat and update.effective_chat.type == 'private':
            return
        
        # Performance monitoring
        start_time = time.time()
        
        try:
            # Check if this is a first-time user interaction (for retroactive checks)
            user_id = update.message.from_user.id
            chat_id = update.effective_chat.id
            
            # Process the message
            await self._process_user_message(update.message, context)
            self._stats['messages_processed'] += 1
            
            # Track processing time
            processing_time = time.time() - start_time
            self._processing_times.append(processing_time)
            self._stats['processing_time_total'] += processing_time
            
            # Keep only recent processing times for average calculation
            if len(self._processing_times) > 100:
                self._processing_times = self._processing_times[-50:]
            
            # Update average processing time
            if self._processing_times:
                self._stats['processing_time_avg'] = sum(self._processing_times) / len(self._processing_times)
            
            # Performance safeguard: Log warning if processing is slow
            if processing_time > self._max_processing_time:
                logger.warning(f"Slow leveling processing: {processing_time:.3f}s (max: {self._max_processing_time:.3f}s)")
            
            # Performance safeguard: Emergency circuit breaker for extremely slow processing
            if processing_time > (self._max_processing_time * 5):  # 500ms
                logger.error(f"Emergency: Extremely slow leveling processing detected: {processing_time:.3f}s")
                self._stats['errors'] += 1
                # Consider temporarily disabling the service if this happens frequently
                
        except Exception as e:
            logger.error(f"Error processing message for leveling: {e}", exc_info=True)
            self._stats['errors'] += 1
            # Don't re-raise to avoid disrupting other message handlers
    
    async def _process_user_message(self, message: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Process a user message for XP and achievements.
        
        Args:
            message: Telegram message to process
            context: Bot context
        """
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Calculate XP for this message
        sender_xp, thanked_users_xp = self.xp_calculator.calculate_total_message_xp(message)
        
        # Process XP for message sender
        if sender_xp > 0:
            await self._award_xp_to_user(user_id, chat_id, sender_xp, message, context)
        
        # Process XP for thanked users
        for thanked_user_id, xp_amount in thanked_users_xp.items():
            await self._award_xp_to_user(thanked_user_id, chat_id, xp_amount, message, context, is_thanks=True)
    
    async def _award_xp_to_user(
        self, 
        user_id: UserId, 
        chat_id: ChatId, 
        xp_amount: int, 
        message: Message, 
        context: ContextTypes.DEFAULT_TYPE,
        is_thanks: bool = False
    ) -> None:
        """
        Award XP to a user and check for level ups and achievements.
        
        Args:
            user_id: User to award XP to
            chat_id: Chat where the activity occurred
            xp_amount: Amount of XP to award
            message: Original message that triggered the XP
            context: Bot context for sending notifications
            is_thanks: Whether this is a thanks XP award (for thanked user)
        """
        # Apply rate limiting if enabled
        if self._service_config.get('rate_limiting_enabled', False):
            if not self._check_rate_limit(user_id, xp_amount):
                self._stats['rate_limited'] += 1
                logger.debug(f"Rate limited user {user_id} for {xp_amount} XP")
                return
        
        # Performance safeguard: Skip processing if XP amount is invalid
        if xp_amount <= 0:
            logger.debug(f"Skipping XP award for user {user_id}: invalid amount {xp_amount}")
            return
        
        try:
            # Get or create user stats with error handling
            user_stats = await self.user_stats_repo.get_user_stats(user_id, chat_id)
            if not user_stats:
                # Ensure user exists in main users table before creating leveling stats
                await self._ensure_user_exists(user_id, message)
                user_stats = await self.user_stats_repo.create_user_stats(user_id, chat_id)
                
                # For new users, perform retroactive achievement check
                if user_stats:
                    await self._perform_retroactive_checks(user_id, chat_id)
            
            # Store old level for level-up detection
            old_level = user_stats.level
            old_xp = user_stats.xp
            
            # Award XP and update activity counters
            user_stats.add_xp(xp_amount)
            self._update_activity_counters(user_stats, message, is_thanks)
            
            # Check for level up
            new_level = self.level_manager.calculate_level(user_stats.xp)
            level_up_result = None
            
            if new_level > old_level:
                user_stats.level = new_level
                level_up_result = LevelUpResult(
                    user_id=user_id,
                    old_level=old_level,
                    new_level=new_level,
                    total_xp=user_stats.xp
                )
                self._stats['levels_gained'] += 1
                logger.info(f"User {user_id} leveled up from {old_level} to {new_level}")
            
            # Save updated stats with transaction safety
            await self.user_stats_repo.update_user_stats(user_stats)
            self._stats['xp_awarded'] += xp_amount
            
            # Check for new achievements
            new_achievements = await self.achievement_engine.check_achievements(user_stats)
            if new_achievements:
                self._stats['achievements_unlocked'] += len(new_achievements)
                logger.info(f"User {user_id} unlocked {len(new_achievements)} achievements")
            
            # Send notifications (with error boundary)
            await self._send_notifications(
                level_up_result, 
                new_achievements, 
                message, 
                context
            )
            
        except Exception as e:
            logger.error(f"Error awarding XP to user {user_id}: {e}", exc_info=True)
            self._stats['errors'] += 1
            # Don't re-raise to avoid disrupting message processing
    
    def _update_activity_counters(self, user_stats: UserStats, message: Message, is_thanks: bool = False) -> None:
        """
        Update activity counters based on message content.
        
        Args:
            user_stats: User statistics to update
            message: Message to analyze
            is_thanks: Whether this is a thanks XP award (for thanked user)
        """
        if is_thanks:
            # This is XP being awarded to a thanked user
            user_stats.increment_thanks()
        else:
            # This is XP being awarded to the message sender
            user_stats.increment_messages()
            
            # Check for links
            if self.xp_calculator.has_links(message):
                user_stats.increment_links()
    
    async def _send_notifications(
        self,
        level_up_result: Optional[LevelUpResult],
        new_achievements: List[Any],
        original_message: Message,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Send level up and achievement notifications.
        
        Args:
            level_up_result: Level up information if user leveled up
            new_achievements: List of newly unlocked achievements
            original_message: Original message that triggered the notifications
            context: Bot context for sending messages
        """
        if not self._service_config.get('notifications_enabled', True) or not self.notification_service:
            return
        
        try:
            user = original_message.from_user
            if not user:
                logger.warning("Cannot send notifications: no user info in message")
                return
            
            # Send level up notification
            if level_up_result:
                await self.notification_service.send_level_up_notification(
                    level_up_result, user, original_message, context
                )
            
            # Send achievement notifications (batch multiple achievements if applicable)
            if new_achievements:
                await self.notification_service.send_multiple_achievements_notification(
                    new_achievements, user, original_message, context
                )
                
        except Exception as e:
            logger.error(f"Error sending notifications: {e}", exc_info=True)
    

    
    async def get_user_profile(self, user_id: UserId, chat_id: ChatId) -> Optional[UserProfile]:
        """
        Get a user's profile with stats and achievements.
        
        Args:
            user_id: User ID
            chat_id: Chat ID
            
        Returns:
            UserProfile object or None if user not found
        """
        if not self._initialized:
            return None
        
        try:
            # Get user stats
            user_stats = await self.user_stats_repo.get_user_stats(user_id, chat_id)
            if not user_stats:
                return None
            
            # Recalculate level based on current XP (retroactive)
            await self.recalculate_user_level(user_id, chat_id)
            
            # Check for any missing achievements (retroactive)
            await self.check_retroactive_achievements(user_id, chat_id)
            
            # Get updated user stats after retroactive checks
            user_stats = await self.user_stats_repo.get_user_stats(user_id, chat_id)
            if not user_stats:
                return None
            
            # Get user achievements
            achievements = await self.achievement_repo.get_user_achievements(user_id, chat_id)
            
            # Calculate next level progress
            next_level_xp = self.level_manager.get_level_threshold(user_stats.level + 1)
            current_level_xp = self.level_manager.get_level_threshold(user_stats.level)
            progress_xp = user_stats.xp - current_level_xp
            required_xp = next_level_xp - current_level_xp
            progress_percentage = (progress_xp / required_xp) * 100 if required_xp > 0 else 100
            
            # Create profile
            profile = UserProfile(
                user_id=user_id,
                username=None,  # Will be filled by command handler
                level=user_stats.level,
                xp=user_stats.xp,
                next_level_xp=next_level_xp,
                progress_percentage=progress_percentage,
                achievements=[ach.achievement for ach in achievements],
                stats={
                    'messages_count': user_stats.messages_count,
                    'links_shared': user_stats.links_shared,
                    'thanks_received': user_stats.thanks_received
                }
            )
            
            return profile
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}", exc_info=True)
            return None
    
    async def get_leaderboard(self, chat_id: ChatId, limit: int = 10) -> List[UserProfile]:
        """
        Get chat leaderboard sorted by XP.
        
        Args:
            chat_id: Chat ID
            limit: Maximum number of users to return
            
        Returns:
            List of UserProfile objects sorted by XP (descending)
        """
        if not self._initialized:
            return []
        
        try:
            user_stats_list = await self.user_stats_repo.get_leaderboard(chat_id, limit)
            profiles = []
            
            for rank, user_stats in enumerate(user_stats_list, 1):
                # Get achievements for this user
                achievements = await self.achievement_repo.get_user_achievements(
                    user_stats.user_id, 
                    chat_id
                )
                
                # Calculate progress
                next_level_xp = self.level_manager.get_level_threshold(user_stats.level + 1)
                current_level_xp = self.level_manager.get_level_threshold(user_stats.level)
                progress_xp = user_stats.xp - current_level_xp
                required_xp = next_level_xp - current_level_xp
                progress_percentage = (progress_xp / required_xp) * 100 if required_xp > 0 else 100
                
                profile = UserProfile(
                    user_id=user_stats.user_id,
                    username=None,  # Will be filled by command handler
                    level=user_stats.level,
                    xp=user_stats.xp,
                    next_level_xp=next_level_xp,
                    progress_percentage=progress_percentage,
                    achievements=[ach.achievement for ach in achievements],
                    stats={
                        'messages_count': user_stats.messages_count,
                        'links_shared': user_stats.links_shared,
                        'thanks_received': user_stats.thanks_received
                    },
                    rank=rank
                )
                profiles.append(profile)
            
            return profiles
            
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}", exc_info=True)
            return []
    
    async def _load_service_configuration(self) -> None:
        """Load service configuration from config manager."""
        try:
            if self.config_manager:
                # Load leveling system configuration
                config = await self.config_manager.get_config(module_name='leveling_system')
                self._service_config = config.get('overrides', {}) if config else {}
                
                # Apply default values for missing configuration
                defaults = {
                    'enabled': True,
                    'level_base_xp': 50,
                    'level_multiplier': 2.0,
                    'notifications_enabled': True,
                    'rate_limiting_enabled': False,
                    'max_xp_per_minute': 10
                }
                
                # Merge defaults with loaded config
                for key, default_value in defaults.items():
                    if key not in self._service_config:
                        self._service_config[key] = default_value
            else:
                # Default configuration
                self._service_config = {
                    'enabled': True,
                    'level_base_xp': 50,
                    'level_multiplier': 2.0,
                    'notifications_enabled': True,
                    'rate_limiting_enabled': False,
                    'max_xp_per_minute': 10
                }
            
            self._enabled = self._service_config.get('enabled', True)
            logger.info(f"Loaded leveling service configuration: enabled={self._enabled}")
            
        except Exception as e:
            logger.error(f"Error loading service configuration: {e}", exc_info=True)
            # Use defaults on error
            self._service_config = {
                'enabled': True,
                'level_base_xp': 50,
                'level_multiplier': 2.0,
                'notifications_enabled': True,
                'rate_limiting_enabled': False,
                'max_xp_per_minute': 10
            }
            self._enabled = True
    
    def _check_rate_limit(self, user_id: int, xp_amount: int) -> bool:
        """
        Check if user is within rate limits for XP earning.
        
        Enhanced rate limiting with sliding window and burst protection.
        
        Args:
            user_id: User ID to check
            xp_amount: Amount of XP being awarded
            
        Returns:
            True if within limits, False if rate limited
        """
        current_time = time.time()
        max_xp = self._service_config.get('max_xp_per_minute', self._max_xp_per_window)
        
        # Initialize user tracking if not exists
        if user_id not in self._user_xp_timestamps:
            self._user_xp_timestamps[user_id] = []
        
        # Clean old timestamps outside the window (sliding window)
        window_start = current_time - self._rate_limit_window
        old_count = len(self._user_xp_timestamps[user_id])
        self._user_xp_timestamps[user_id] = [
            timestamp for timestamp in self._user_xp_timestamps[user_id]
            if timestamp > window_start
        ]
        
        # Log cleanup if significant
        cleaned_count = old_count - len(self._user_xp_timestamps[user_id])
        if cleaned_count > 0:
            logger.debug(f"Cleaned {cleaned_count} old XP timestamps for user {user_id}")
        
        # Calculate current XP in window
        current_xp_in_window = len(self._user_xp_timestamps[user_id])
        
        # Enhanced burst protection: limit rapid consecutive awards
        if len(self._user_xp_timestamps[user_id]) >= 3:
            # Check if last 3 awards were within 10 seconds (burst detection)
            recent_timestamps = self._user_xp_timestamps[user_id][-3:]
            if current_time - recent_timestamps[0] < 10:
                logger.debug(f"Burst protection triggered for user {user_id}")
                return False
        
        # Check if adding this XP would exceed the limit
        if current_xp_in_window + xp_amount > max_xp:
            logger.debug(f"Rate limit exceeded for user {user_id}: {current_xp_in_window + xp_amount} > {max_xp}")
            return False
        
        # Add timestamps for the XP being awarded
        for _ in range(xp_amount):
            self._user_xp_timestamps[user_id].append(current_time)
        
        # Periodic cleanup of user tracking to prevent memory leaks
        if len(self._user_xp_timestamps) > 1000:
            self._cleanup_rate_limit_tracking()
        
        return True
    
    def _cleanup_rate_limit_tracking(self) -> None:
        """
        Clean up rate limiting tracking to prevent memory leaks.
        
        Removes tracking for users who haven't been active recently.
        """
        current_time = time.time()
        cleanup_threshold = current_time - (self._rate_limit_window * 2)  # 2x window
        
        users_to_remove = []
        for user_id, timestamps in self._user_xp_timestamps.items():
            if not timestamps or timestamps[-1] < cleanup_threshold:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self._user_xp_timestamps[user_id]
        
        if users_to_remove:
            logger.debug(f"Cleaned up rate limiting tracking for {len(users_to_remove)} inactive users")
    
    async def _ensure_user_exists(self, user_id: UserId, message: Message) -> None:
        """
        Ensure user exists in the main users table before creating leveling stats.
        
        This method creates a user record if it doesn't exist, which is required
        due to foreign key constraints in the user_chat_stats table.
        
        Args:
            user_id: User ID to ensure exists
            message: Message containing user information
        """
        try:
            from modules.database import Database
            
            # Extract user information from message
            user = message.from_user
            if not user:
                logger.warning(f"Cannot ensure user exists: no user info in message for user_id {user_id}")
                return
            
            username = user.username
            first_name = user.first_name or ""
            last_name = user.last_name or ""
            
            # Try to create user record (will be ignored if already exists)
            await Database.save_user(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            
            logger.debug(f"Ensured user {user_id} exists in users table")
            
        except Exception as e:
            logger.error(f"Error ensuring user {user_id} exists: {e}", exc_info=True)
            # Don't re-raise as this is a helper method
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        Get service performance statistics.
        
        Returns:
            Dictionary with service statistics
        """
        return {
            'initialized': self._initialized,
            'enabled': self._enabled,
            'stats': self._stats.copy(),
            'config': self._service_config.copy(),
            'rate_limiting': {
                'enabled': self._service_config.get('rate_limiting_enabled', False),
                'max_xp_per_minute': self._service_config.get('max_xp_per_minute', self._max_xp_per_window),
                'active_users': len(self._user_xp_timestamps)
            }
        }
    
    def is_enabled(self) -> bool:
        """Check if the leveling service is enabled."""
        return self._initialized and self._enabled
    
    async def check_retroactive_achievements(self, user_id: UserId, chat_id: ChatId) -> List[Any]:
        """
        Check and unlock achievements based on current user stats (retroactively).
        
        This method is called when a user requests their profile or when the system
        needs to ensure all achievements are properly unlocked based on current stats.
        
        Args:
            user_id: User ID to check
            chat_id: Chat ID
            
        Returns:
            List of newly unlocked achievements
        """
        if not self._initialized or not self._enabled:
            return []
        
        try:
            # Get current user stats
            user_stats = await self.user_stats_repo.get_user_stats(user_id, chat_id)
            if not user_stats:
                return []
            
            # Check for achievements based on current stats
            new_achievements = await self.achievement_engine.check_achievements(user_stats)
            
            if new_achievements:
                logger.info(f"Retroactively unlocked {len(new_achievements)} achievements for user {user_id}")
                self._stats['achievements_unlocked'] += len(new_achievements)
            
            return new_achievements
            
        except Exception as e:
            logger.error(f"Error checking retroactive achievements for user {user_id}: {e}", exc_info=True)
            return []
    
    async def recalculate_user_level(self, user_id: UserId, chat_id: ChatId) -> Optional[int]:
        """
        Recalculate and update user level based on current XP.
        
        This ensures level is consistent with XP, useful for retroactive updates.
        
        Args:
            user_id: User ID
            chat_id: Chat ID
            
        Returns:
            New level if updated, None if no change or error
        """
        if not self._initialized or not self._enabled:
            return None
        
        try:
            # Get current user stats
            user_stats = await self.user_stats_repo.get_user_stats(user_id, chat_id)
            if not user_stats:
                return None
            
            # Calculate correct level based on current XP
            correct_level = self.level_manager.calculate_level(user_stats.xp)
            
            # Update if different
            if correct_level != user_stats.level:
                old_level = user_stats.level
                user_stats.level = correct_level
                await self.user_stats_repo.update_user_stats(user_stats)
                
                logger.info(f"Recalculated level for user {user_id}: {old_level} -> {correct_level}")
                return correct_level
            
            return None
            
        except Exception as e:
            logger.error(f"Error recalculating level for user {user_id}: {e}", exc_info=True)
            return None
    
    async def _perform_retroactive_checks(self, user_id: UserId, chat_id: ChatId) -> None:
        """
        Perform retroactive checks for levels and achievements based on current database stats.
        
        This method is called when processing messages for existing users to ensure
        their levels and achievements are up to date with their current stats.
        
        Args:
            user_id: User ID to check
            chat_id: Chat ID
        """
        if not self._initialized or not self._enabled:
            return
        
        try:
            # Recalculate level based on current XP
            await self.recalculate_user_level(user_id, chat_id)
            
            # Check for missing achievements based on current stats
            await self.check_retroactive_achievements(user_id, chat_id)
            
            logger.debug(f"Completed retroactive checks for user {user_id} in chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error performing retroactive checks for user {user_id}: {e}", exc_info=True)
    
    async def perform_bulk_retroactive_checks(self, chat_id: ChatId, limit: int = 100) -> Dict[str, int]:
        """
        Perform retroactive checks for all users in a chat.
        
        This method can be used to update all users' levels and achievements
        based on their current database stats. Useful after system updates
        or when enabling the leveling system for an existing chat.
        
        Args:
            chat_id: Chat ID to process
            limit: Maximum number of users to process in one batch
            
        Returns:
            Dictionary with statistics about the retroactive checks
        """
        if not self._initialized or not self._enabled:
            return {'error': 'Service not initialized or disabled'}
        
        stats = {
            'users_processed': 0,
            'levels_updated': 0,
            'achievements_unlocked': 0,
            'errors': 0
        }
        
        try:
            # Get all users in the chat (limited batch)
            user_stats_list = await self.user_stats_repo.get_leaderboard(chat_id, limit)
            
            for user_stats in user_stats_list:
                try:
                    # Perform retroactive checks for each user
                    old_level = user_stats.level
                    
                    # Recalculate level
                    new_level = await self.recalculate_user_level(user_stats.user_id, chat_id)
                    if new_level and new_level != old_level:
                        stats['levels_updated'] += 1
                    
                    # Check achievements
                    new_achievements = await self.check_retroactive_achievements(user_stats.user_id, chat_id)
                    stats['achievements_unlocked'] += len(new_achievements)
                    
                    stats['users_processed'] += 1
                    
                except Exception as e:
                    logger.error(f"Error in retroactive check for user {user_stats.user_id}: {e}")
                    stats['errors'] += 1
            
            logger.info(f"Bulk retroactive checks completed for chat {chat_id}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error performing bulk retroactive checks for chat {chat_id}: {e}", exc_info=True)
            stats['errors'] += 1
            return stats
    
    async def _perform_startup_retroactive_checks(self) -> None:
        """
        Perform retroactive checks on startup for existing users.
        
        This method can be called during service initialization to ensure
        all existing users have correct levels and achievements based on
        their current database stats.
        
        Note: This is an expensive operation and should be used carefully.
        """
        try:
            logger.info("Starting retroactive checks for existing users...")
            
            # Get a sample of active chats (limit to prevent startup delays)
            # This would need to be implemented based on your database schema
            # For now, we'll skip this to avoid startup delays
            
            logger.info("Startup retroactive checks completed (skipped for performance)")
            
        except Exception as e:
            logger.error(f"Error during startup retroactive checks: {e}", exc_info=True)