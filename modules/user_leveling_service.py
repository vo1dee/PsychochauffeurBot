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
from modules.service_error_boundary import with_error_boundary
from modules.service_error_boundary import ServiceErrorBoundary, health_monitor
from modules.caching_system import cache_manager, CacheConfig, CacheBackend
from modules.performance_monitor import performance_monitor, monitor_performance
from modules.leveling_cache import leveling_cache
from modules.leveling_performance_monitor import leveling_performance_monitor, record_processing_time, record_database_time

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
    
    def __init__(self, config_manager=None, database=None):
        """
        Initialize the UserLevelingService.
        
        Args:
            config_manager: Configuration manager for system settings
            database: Database service for data persistence
        """
        self.config_manager = config_manager
        self.database = database
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
        
        # Enhanced error handling and resilience
        self.error_boundary = health_monitor.register_service("user_leveling_service")
        
        # Caching system for performance optimization
        self._cache = None
        self._cache_config = CacheConfig(
            backend=CacheBackend.MEMORY,
            default_ttl=300,  # 5 minutes
            max_size=1000,
            key_prefix="leveling"
        )
        
        # Performance tracking with enhanced metrics
        self._stats = {
            'messages_processed': 0,
            'xp_awarded': 0,
            'levels_gained': 0,
            'achievements_unlocked': 0,
            'errors': 0,
            'rate_limited': 0,
            'processing_time_total': 0.0,
            'processing_time_avg': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'database_retries': 0,
            'circuit_breaker_trips': 0
        }
        
        # Rate limiting with enhanced tracking
        self._user_xp_timestamps: Dict[int, List[float]] = {}
        self._rate_limit_window = 60  # 1 minute window
        self._max_xp_per_window = 10  # Max XP per user per minute
        
        # Performance monitoring with thresholds
        self._processing_times: List[float] = []
        self._max_processing_time = 0.1  # 100ms max processing time
        self._performance_degradation_threshold = 0.5  # 500ms critical threshold
        
        # Error recovery and fallback mechanisms
        self._fallback_enabled = True
        self._last_health_check = datetime.now()
        self._health_check_interval = 300  # 5 minutes
        
        logger.info("UserLevelingService instance created with enhanced error handling and performance optimization")
    
    async def initialize(self) -> None:
        """Initialize the leveling service with all components and enhanced error handling."""
        if self._initialized:
            logger.debug("UserLevelingService already initialized, skipping")
            return
        
        logger.info("Initializing UserLevelingService with enhanced error handling...")
        
        try:
            # Load service configuration with error handling
            await self._load_service_configuration()
            
            # Initialize caching system
            await self._initialize_caching()
            
            # Initialize core components with error boundaries
            await self._initialize_core_components()
            
            # Initialize repositories with retry mechanisms
            await self._initialize_repositories()
            
            # Initialize achievement engine with fallback handling
            await self._initialize_achievement_engine()
            
            # Initialize notification service
            await self._initialize_notification_service()
            
            # Initialize achievement definitions in database with retries
            await self._initialize_achievement_definitions()
            
            # Setup performance monitoring
            await self._setup_performance_monitoring()
            
            # Register error boundary fallbacks
            await self._register_fallback_handlers()
            
            # Perform health check
            await self._perform_initial_health_check()
            
            self._initialized = True
            logger.info("UserLevelingService initialized successfully with enhanced features")
            
        except Exception as e:
            logger.error(f"Failed to initialize UserLevelingService: {e}", exc_info=True)
            self._stats['errors'] += 1
            # Try to initialize in degraded mode
            await self._initialize_degraded_mode()
            raise
    
    async def _initialize_caching(self) -> None:
        """Initialize caching system for performance optimization."""
        try:
            self._cache = cache_manager.get_or_create_cache("leveling_cache", self._cache_config)
            
            # Warm up the specialized leveling cache
            await self._warm_up_leveling_cache()
            
            logger.info("Caching system initialized for leveling service with cache warming")
        except Exception as e:
            logger.warning(f"Failed to initialize caching system: {e}")
            self._cache = None
    
    async def _warm_up_leveling_cache(self) -> None:
        """Warm up the leveling cache with frequently accessed data."""
        try:
            # Define cache warming functions
            async def load_achievements():
                if self.achievement_repo:
                    return await self.achievement_repo.get_all_achievements()
                return []
            
            async def load_user_stats(user_id: UserId, chat_id: ChatId):
                if self.user_stats_repo:
                    return await self.user_stats_repo.get_user_stats(user_id, chat_id)
                return None
            
            # Perform cache warming
            await leveling_cache.warm_up_cache(load_user_stats, load_achievements)
            
            logger.info("Leveling cache warmed up successfully")
            
        except Exception as e:
            logger.warning(f"Failed to warm up leveling cache: {e}")
    
    async def _initialize_core_components(self) -> None:
        """Initialize core components with error handling."""
        try:
            self.xp_calculator = XPCalculator()
            self.level_manager = LevelManager(
                base_xp=self._service_config.get('level_base_xp', 50),
                multiplier=self._service_config.get('level_multiplier', 2.0)
            )
            logger.info("Core components initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize core components: {e}")
            raise
    
    async def _initialize_repositories(self) -> None:
        """Initialize repositories with enhanced error handling."""
        try:
            self.user_stats_repo = UserStatsRepository()
            self.achievement_repo = AchievementRepository()
            logger.info("Repositories initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize repositories: {e}")
            raise
    
    async def _initialize_achievement_engine(self) -> None:
        """Initialize achievement engine with fallback handling."""
        try:
            self.achievement_engine = AchievementEngine(self.achievement_repo)
            logger.info("Achievement engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize achievement engine: {e}")
            # Continue without achievement engine in degraded mode
            self.achievement_engine = None
    
    async def _initialize_notification_service(self) -> None:
        """Initialize notification service."""
        try:
            notification_config = self._service_config.get('notifications', {})
            self.notification_service = LevelingNotificationService(notification_config)
            logger.info("Notification service initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize notification service: {e}")
            self.notification_service = None
    
    async def _initialize_achievement_definitions(self) -> None:
        """Initialize achievement definitions with retry mechanism."""
        if not self.achievement_engine:
            logger.warning("Skipping achievement definitions initialization - engine not available")
            return
        
        async def init_achievements():
            await self.achievement_engine.initialize_achievement_definitions()
        
        try:
            await self.error_boundary.execute_with_boundary(
                operation=init_achievements,
                operation_name="initialize_achievement_definitions",
                timeout=30.0
            )
            logger.info("Achievement definitions initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize achievement definitions: {e}")
            # Continue without achievements in degraded mode
    
    async def _setup_performance_monitoring(self) -> None:
        """Setup performance monitoring and metrics collection."""
        try:
            # Register performance metrics
            performance_monitor.record_metric("leveling_service_initialized", 1)
            
            # Setup periodic health checks
            self._last_health_check = datetime.now()
            
            logger.info("Performance monitoring setup completed")
        except Exception as e:
            logger.warning(f"Failed to setup performance monitoring: {e}")
    
    async def _register_fallback_handlers(self) -> None:
        """Register fallback handlers for error boundary."""
        try:
            # Register fallback for user stats retrieval
            async def fallback_get_user_stats():
                return None
            
            self.error_boundary.register_fallback("get_user_stats", fallback_get_user_stats)
            
            # Register fallback for XP awarding
            async def fallback_award_xp():
                logger.warning("Using fallback XP awarding - stats not persisted")
                return None
            
            self.error_boundary.register_fallback("award_xp", fallback_award_xp)
            
            logger.info("Fallback handlers registered successfully")
        except Exception as e:
            logger.warning(f"Failed to register fallback handlers: {e}")
    
    async def _perform_initial_health_check(self) -> None:
        """Perform initial health check of the service."""
        try:
            async def health_check():
                # Test database connectivity
                if self.user_stats_repo:
                    # Try a simple database operation
                    await self.user_stats_repo.get_user_stats(0, 0)  # This should return None
                return True
            
            is_healthy = await self.error_boundary.perform_health_check(health_check)
            if is_healthy:
                logger.info("Initial health check passed")
            else:
                logger.warning("Initial health check failed - service may be degraded")
        except Exception as e:
            logger.warning(f"Initial health check error: {e}")
    
    async def _initialize_degraded_mode(self) -> None:
        """Initialize service in degraded mode with minimal functionality."""
        try:
            logger.warning("Initializing UserLevelingService in degraded mode")
            
            # Initialize only essential components
            self.xp_calculator = XPCalculator()
            self.level_manager = LevelManager()
            
            # Disable features that require database
            self._fallback_enabled = True
            self._enabled = False  # Disable processing until recovery
            
            logger.info("UserLevelingService initialized in degraded mode")
        except Exception as e:
            logger.error(f"Failed to initialize degraded mode: {e}")

    async def shutdown(self) -> None:
        """Shutdown the leveling service and cleanup resources."""
        logger.info("Shutting down UserLevelingService...")
        
        try:
            # Log final statistics with enhanced metrics
            logger.info(f"UserLevelingService final statistics: {self._stats}")
            
            # Generate performance report
            if self._initialized:
                await self._generate_shutdown_report()
            
            # Cleanup caching
            if self._cache:
                await self._cache.clear()
                self._cache = None
            
            # Cleanup components
            self.xp_calculator = None
            self.level_manager = None
            self.achievement_engine = None
            self.user_stats_repo = None
            self.achievement_repo = None
            self.notification_service = None
            
            # Reset error boundary
            if self.error_boundary:
                self.error_boundary.reset()
            
            self._initialized = False
            logger.info("UserLevelingService shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during UserLevelingService shutdown: {e}", exc_info=True)
    
    async def _generate_shutdown_report(self) -> None:
        """Generate a comprehensive shutdown report."""
        try:
            report = {
                'service_name': 'user_leveling_service',
                'shutdown_time': datetime.now().isoformat(),
                'uptime_seconds': (datetime.now() - self._last_health_check).total_seconds(),
                'statistics': self._stats,
                'error_boundary_stats': self.error_boundary.get_health_status().__dict__ if self.error_boundary else None,
                'cache_stats': self._cache.get_stats().__dict__ if self._cache else None
            }
            
            logger.info(f"Shutdown report: {report}")
            
            # Record final metrics
            performance_monitor.record_metric("leveling_service_shutdown", 1)
            performance_monitor.record_metric("leveling_service_uptime", report['uptime_seconds'])
            
        except Exception as e:
            logger.warning(f"Failed to generate shutdown report: {e}")
    
    @monitor_performance("leveling_process_message")
    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Process a message for XP calculation and leveling updates.
        
        Enhanced with comprehensive error handling, caching, and performance monitoring.
        
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
        
        # Performance monitoring with enhanced metrics
        start_time = time.time()
        user_id = update.message.from_user.id
        chat_id = update.effective_chat.id
        
        # Execute with error boundary protection
        async def process_operation():
            await self._process_user_message(update.message, context)
        
        try:
            result = await self.error_boundary.execute_with_boundary(
                operation=process_operation,
                operation_name="process_message",
                timeout=self._max_processing_time * 10,  # 1 second timeout
                context={
                    'user_id': user_id,
                    'chat_id': chat_id,
                    'message_type': update.message.content_type if hasattr(update.message, 'content_type') else 'text'
                }
            )
            
            if result is not None:
                self._stats['messages_processed'] += 1
            
            # Track processing time with enhanced monitoring
            processing_time = time.time() - start_time
            self._track_processing_time(processing_time)
            
            # Record performance metrics
            performance_monitor.record_metric(
                "leveling_message_processing_time",
                processing_time,
                "seconds",
                {'user_id': str(user_id), 'chat_id': str(chat_id)}
            )
            
            # Performance safeguards with escalating responses
            await self._check_performance_thresholds(processing_time)
            
            # Periodic health checks
            await self._periodic_health_check()
                
        except Exception as e:
            logger.error(f"Error processing message for leveling: {e}", exc_info=True)
            self._stats['errors'] += 1
            
            # Record error metrics
            performance_monitor.record_metric("leveling_processing_errors", 1)
            
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
    
    @with_error_boundary("user_leveling_service", "award_xp_to_user", timeout=5.0)
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
        Enhanced with caching, error handling, and performance optimization.
        
        Args:
            user_id: User to award XP to
            chat_id: Chat where the activity occurred
            xp_amount: Amount of XP to award
            message: Original message that triggered the XP
            context: Bot context for sending notifications
            is_thanks: Whether this is a thanks XP award (for thanked user)
        """
        # Apply enhanced rate limiting
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
            # Get user stats with caching
            user_stats = await self._get_user_stats_cached(user_id, chat_id)
            
            if not user_stats:
                # Ensure user exists and create stats
                await self._ensure_user_exists(user_id, message)
                user_stats = await self._create_user_stats_with_retry(user_id, chat_id)
                
                # For new users, perform retroactive achievement check
                if user_stats:
                    await self._perform_retroactive_checks_safe(user_id, chat_id)
            
            # Store old values for comparison
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
                
                # Record level up metric
                performance_monitor.record_metric("leveling_level_ups", 1, tags={'new_level': str(new_level)})
            
            # Save updated stats with enhanced error handling
            await self._update_user_stats_with_retry(user_stats)
            self._stats['xp_awarded'] += xp_amount
            
            # Invalidate cache for this user
            await self._invalidate_user_cache(user_id, chat_id)
            
            # Check for new achievements with error handling
            new_achievements = await self._check_achievements_safe(user_stats)
            if new_achievements:
                self._stats['achievements_unlocked'] += len(new_achievements)
                logger.info(f"User {user_id} unlocked {len(new_achievements)} achievements")
                
                # Record achievement metrics
                performance_monitor.record_metric("leveling_achievements_unlocked", len(new_achievements))
            
            # Send notifications with error boundary
            await self._send_notifications_safe(level_up_result, new_achievements, message, context)
            
        except Exception as e:
            logger.error(f"Error awarding XP to user {user_id}: {e}", exc_info=True)
            self._stats['errors'] += 1
            performance_monitor.record_metric("leveling_xp_award_errors", 1)
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
    

    
    @monitor_performance("leveling_get_user_profile")
    async def get_user_profile(self, user_id: UserId, chat_id: ChatId) -> Optional[UserProfile]:
        """
        Get a user's profile with stats and achievements.
        Enhanced with caching and performance optimization.
        
        Args:
            user_id: User ID
            chat_id: Chat ID
            
        Returns:
            UserProfile object or None if user not found
        """
        if not self._initialized:
            return None
        
        async def get_profile_operation():
            # Get user stats with caching
            user_stats = await self._get_user_stats_cached(user_id, chat_id)
            if not user_stats:
                return None
            
            # Recalculate level based on current XP (retroactive)
            await self.recalculate_user_level(user_id, chat_id)
            
            # Check for any missing achievements (retroactive)
            await self.check_retroactive_achievements(user_id, chat_id)
            
            # Get updated user stats after retroactive checks (with caching)
            user_stats = await self._get_user_stats_cached(user_id, chat_id)
            if not user_stats:
                return None
            
            # Get user achievements with caching
            achievements_data = await leveling_cache.get_user_achievements(user_id, chat_id)
            if achievements_data:
                achievements = [Achievement.from_dict(ach_dict) for ach_dict in achievements_data]
            else:
                # Cache miss - get from database
                user_achievements = await self.achievement_repo.get_user_achievements(user_id, chat_id)
                achievements = [ach.achievement for ach in user_achievements]
                
                # Cache the achievements
                if achievements:
                    await leveling_cache.set_user_achievements(user_id, chat_id, achievements)
            
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
                achievements=achievements,
                stats={
                    'messages_count': user_stats.messages_count,
                    'links_shared': user_stats.links_shared,
                    'thanks_received': user_stats.thanks_received
                }
            )
            
            return profile
        
        try:
            # Execute with error boundary protection
            result = await self.error_boundary.execute_with_boundary(
                operation=get_profile_operation,
                operation_name="get_user_profile",
                timeout=10.0,
                context={'user_id': user_id, 'chat_id': chat_id}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}", exc_info=True)
            performance_monitor.record_metric("leveling_get_profile_errors", 1)
            return None
    
    @monitor_performance("leveling_get_leaderboard")
    async def get_leaderboard(self, chat_id: ChatId, limit: int = 10) -> List[UserProfile]:
        """
        Get chat leaderboard sorted by XP.
        Enhanced with caching and performance optimization.
        
        Args:
            chat_id: Chat ID
            limit: Maximum number of users to return
            
        Returns:
            List of UserProfile objects sorted by XP (descending)
        """
        if not self._initialized:
            return []
        
        async def get_leaderboard_operation():
            # Try cache first
            cached_leaderboard = await leveling_cache.get_leaderboard(chat_id, limit)
            if cached_leaderboard:
                return [UserProfile.from_dict(profile_dict) for profile_dict in cached_leaderboard]
            
            # Cache miss - generate leaderboard
            user_stats_list = await self.user_stats_repo.get_leaderboard(chat_id, limit)
            profiles = []
            
            for rank, user_stats in enumerate(user_stats_list, 1):
                # Get achievements for this user (with caching)
                achievements_data = await leveling_cache.get_user_achievements(user_stats.user_id, chat_id)
                if achievements_data:
                    achievements = [Achievement.from_dict(ach_dict) for ach_dict in achievements_data]
                else:
                    # Cache miss - get from database
                    user_achievements = await self.achievement_repo.get_user_achievements(
                        user_stats.user_id, 
                        chat_id
                    )
                    achievements = [ach.achievement for ach in user_achievements]
                    
                    # Cache the achievements
                    if achievements:
                        await leveling_cache.set_user_achievements(user_stats.user_id, chat_id, achievements)
                
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
                    achievements=achievements,
                    stats={
                        'messages_count': user_stats.messages_count,
                        'links_shared': user_stats.links_shared,
                        'thanks_received': user_stats.thanks_received
                    },
                    rank=rank
                )
                profiles.append(profile)
            
            # Cache the leaderboard
            if profiles:
                profile_dicts = [profile.to_dict() for profile in profiles]
                await leveling_cache.set_leaderboard(chat_id, limit, profile_dicts)
            
            return profiles
        
        try:
            # Execute with error boundary protection
            result = await self.error_boundary.execute_with_boundary(
                operation=get_leaderboard_operation,
                operation_name="get_leaderboard",
                timeout=15.0,
                context={'chat_id': chat_id, 'limit': limit}
            )
            
            return result or []
            
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}", exc_info=True)
            performance_monitor.record_metric("leveling_get_leaderboard_errors", 1)
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
            # Extract user information from message
            user = message.from_user
            if not user:
                logger.warning(f"Cannot ensure user exists: no user info in message for user_id {user_id}")
                return
            
            username = user.username
            first_name = user.first_name or ""
            last_name = user.last_name or ""
            
            # Use injected database service if available, otherwise fall back to static import
            if self.database:
                await self.database.save_user(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
            else:
                # Fallback to static import for backward compatibility
                from modules.database import Database
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
    
    def _track_processing_time(self, processing_time: float) -> None:
        """Track processing time with enhanced monitoring."""
        self._processing_times.append(processing_time)
        self._stats['processing_time_total'] += processing_time
        
        # Keep only recent processing times for average calculation
        if len(self._processing_times) > 100:
            self._processing_times = self._processing_times[-50:]
        
        # Update average processing time
        if self._processing_times:
            self._stats['processing_time_avg'] = sum(self._processing_times) / len(self._processing_times)
        
        # Record in specialized performance monitor
        record_processing_time("message_processing", processing_time)
    
    async def _check_performance_thresholds(self, processing_time: float) -> None:
        """Check performance thresholds and take action if needed."""
        if processing_time > self._max_processing_time:
            logger.warning(f"Slow leveling processing: {processing_time:.3f}s (max: {self._max_processing_time:.3f}s)")
            performance_monitor.record_metric("leveling_slow_processing", 1)
        
        # Critical performance degradation
        if processing_time > self._performance_degradation_threshold:
            logger.error(f"Critical: Extremely slow leveling processing: {processing_time:.3f}s")
            self._stats['errors'] += 1
            performance_monitor.record_metric("leveling_critical_slow_processing", 1)
            
            # Consider circuit breaker activation
            self._stats['circuit_breaker_trips'] += 1
    
    async def _periodic_health_check(self) -> None:
        """Perform periodic health checks."""
        now = datetime.now()
        if (now - self._last_health_check).total_seconds() > self._health_check_interval:
            try:
                is_healthy = await self.error_boundary.perform_health_check()
                if not is_healthy:
                    logger.warning("Health check failed - service may be degraded")
                    performance_monitor.record_metric("leveling_health_check_failed", 1)
                else:
                    performance_monitor.record_metric("leveling_health_check_passed", 1)
                
                self._last_health_check = now
            except Exception as e:
                logger.warning(f"Health check error: {e}")
    
    async def _get_user_stats_cached(self, user_id: UserId, chat_id: ChatId) -> Optional[UserStats]:
        """Get user stats with intelligent caching support."""
        try:
            # Try specialized leveling cache first
            cached_data = await leveling_cache.get_user_stats(user_id, chat_id)
            if cached_data:
                self._stats['cache_hits'] += 1
                return UserStats.from_dict(cached_data)
            
            # Cache miss - get from database
            self._stats['cache_misses'] += 1
            user_stats = await self.user_stats_repo.get_user_stats(user_id, chat_id)
            
            # Cache the result with intelligent TTL
            if user_stats:
                await leveling_cache.set_user_stats(user_id, chat_id, user_stats)
            
            return user_stats
            
        except Exception as e:
            logger.warning(f"Cache error for user stats: {e}")
            # Fallback to direct database access
            return await self.user_stats_repo.get_user_stats(user_id, chat_id)
    
    async def _create_user_stats_with_retry(self, user_id: UserId, chat_id: ChatId) -> Optional[UserStats]:
        """Create user stats with retry mechanism."""
        async def create_operation():
            return await self.user_stats_repo.create_user_stats(user_id, chat_id)
        
        try:
            result = await self.error_boundary.execute_with_boundary(
                operation=create_operation,
                operation_name="create_user_stats",
                timeout=10.0
            )
            return result
        except Exception as e:
            logger.error(f"Failed to create user stats after retries: {e}")
            return None
    
    async def _update_user_stats_with_retry(self, user_stats: UserStats) -> None:
        """Update user stats with retry mechanism."""
        async def update_operation():
            await self.user_stats_repo.update_user_stats(user_stats)
        
        try:
            await self.error_boundary.execute_with_boundary(
                operation=update_operation,
                operation_name="update_user_stats",
                timeout=10.0
            )
            self._stats['database_retries'] += 1
        except Exception as e:
            logger.error(f"Failed to update user stats after retries: {e}")
            raise
    
    async def _invalidate_user_cache(self, user_id: UserId, chat_id: ChatId) -> None:
        """Invalidate cached user data with intelligent cache management."""
        try:
            # Use specialized leveling cache invalidation
            await leveling_cache.invalidate_user_related_caches(user_id, chat_id)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
    
    async def _check_achievements_safe(self, user_stats: UserStats) -> List[Any]:
        """Check achievements with error handling."""
        if not self.achievement_engine:
            return []
        
        try:
            return await self.achievement_engine.check_achievements(user_stats)
        except Exception as e:
            logger.warning(f"Achievement check failed: {e}")
            return []
    
    async def _send_notifications_safe(
        self,
        level_up_result: Optional[LevelUpResult],
        new_achievements: List[Any],
        message: Message,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Send notifications with error handling."""
        if not self.notification_service:
            return
        
        try:
            await self._send_notifications(level_up_result, new_achievements, message, context)
        except Exception as e:
            logger.warning(f"Notification sending failed: {e}")
    
    async def _perform_retroactive_checks_safe(self, user_id: UserId, chat_id: ChatId) -> None:
        """Perform retroactive checks with error handling."""
        try:
            await self._perform_retroactive_checks(user_id, chat_id)
        except Exception as e:
            logger.warning(f"Retroactive checks failed for user {user_id}: {e}")

    def get_service_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive service performance statistics.
        
        Returns:
            Dictionary with enhanced service statistics
        """
        health_status = self.error_boundary.get_health_status() if self.error_boundary else None
        cache_stats = self._cache.get_stats() if self._cache else None
        
        return {
            'initialized': self._initialized,
            'enabled': self._enabled,
            'stats': self._stats.copy(),
            'config': self._service_config.copy(),
            'rate_limiting': {
                'enabled': self._service_config.get('rate_limiting_enabled', False),
                'max_xp_per_minute': self._service_config.get('max_xp_per_minute', self._max_xp_per_window),
                'active_users': len(self._user_xp_timestamps)
            },
            'health_status': health_status.__dict__ if health_status else None,
            'cache_stats': cache_stats.__dict__ if cache_stats else None,
            'leveling_cache_metrics': leveling_cache.get_cache_metrics(),
            'performance_monitoring': leveling_performance_monitor.get_health_status(),
            'performance': {
                'avg_processing_time': self._stats.get('processing_time_avg', 0),
                'max_processing_time': self._max_processing_time,
                'degradation_threshold': self._performance_degradation_threshold,
                'recent_processing_times': self._processing_times[-10:] if self._processing_times else []
            },
            'error_recovery': {
                'fallback_enabled': self._fallback_enabled,
                'last_health_check': self._last_health_check.isoformat(),
                'circuit_breaker_trips': self._stats.get('circuit_breaker_trips', 0)
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