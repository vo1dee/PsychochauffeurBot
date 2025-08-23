"""
Achievement system engine for the user leveling system.

This module provides the core achievement system functionality including
achievement definitions, condition checking, and unlocking logic.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
import re

from modules.leveling_models import Achievement, UserStats, UserAchievement
from modules.repositories import AchievementRepository
from modules.types import UserId, ChatId

logger = logging.getLogger(__name__)


class AchievementDefinitions:
    """
    Static definitions for all achievements in the system.
    
    Contains all achievement definitions organized by category with their
    conditions and metadata.
    """
    
    @staticmethod
    def get_all_achievements() -> List[Achievement]:
        """
        Get all achievement definitions.
        
        Returns:
            List of all Achievement objects
        """
        achievements = []
        
        # Activity achievements
        achievements.extend(AchievementDefinitions._get_activity_achievements())
        
        # Links and media achievements
        achievements.extend(AchievementDefinitions._get_media_achievements())
        
        # Social interaction achievements
        achievements.extend(AchievementDefinitions._get_social_achievements())
        
        # Rare/special achievements
        achievements.extend(AchievementDefinitions._get_rare_achievements())
        
        # Level achievements
        achievements.extend(AchievementDefinitions._get_level_achievements())
        
        return achievements
    
    @staticmethod
    def _get_activity_achievements() -> List[Achievement]:
        """Get activity-based achievements."""
        return [
            Achievement(
                id="novice",
                title="👶 Новачок",
                description="Надіслав своє перше повідомлення",
                emoji="👶",
                sticker="👶",
                condition_type="messages_count",
                condition_value=1,
                category="activity"
            ),
            Achievement(
                id="young_chatter",
                title="🐣 Молодий базіка",
                description="Надіслав 100+ повідомлень",
                emoji="🐣",
                sticker="🐣",
                condition_type="messages_count",
                condition_value=100,
                category="activity"
            ),
            Achievement(
                id="active_talker",
                title="🗣️ Активний співрозмовник",
                description="Надіслав 500+ повідомлень",
                emoji="🗣️",
                sticker="🗣️",
                condition_type="messages_count",
                condition_value=500,
                category="activity"
            ),
            Achievement(
                id="chat_voice",
                title="💬 Голос чату",
                description="Надіслав 1,000+ повідомлень",
                emoji="💬",
                sticker="💬",
                condition_type="messages_count",
                condition_value=1000,
                category="activity"
            ),
            Achievement(
                id="scribe",
                title="🪶 Писар",
                description="Надіслав 5,000+ повідомлень",
                emoji="🪶",
                sticker="🪶",
                condition_type="messages_count",
                condition_value=5000,
                category="activity"
            ),
            Achievement(
                id="psycho_chauffeur",
                title="📜 Психошофьор",
                description="Надіслав 10,000+ повідомлень",
                emoji="📜",
                sticker="📜",
                condition_type="messages_count",
                condition_value=10000,
                category="activity"
            ),
            Achievement(
                id="elder",
                title="🏛️ Старійшина",
                description="Надіслав 20,000+ повідомлень",
                emoji="🏛️",
                sticker="🏛️",
                condition_type="messages_count",
                condition_value=20000,
                category="activity"
            ),
            Achievement(
                id="chat_lord",
                title="👑 Володар чату",
                description="Надіслав 50,000+ повідомлень",
                emoji="👑",
                sticker="👑",
                condition_type="messages_count",
                condition_value=50000,
                category="activity"
            ),
            Achievement(
                id="chat_legend",
                title="🌌 Легенда чату",
                description="Надіслав 100,000+ повідомлень",
                emoji="🌌",
                sticker="🌌",
                condition_type="messages_count",
                condition_value=100000,
                category="activity"
            ),
            Achievement(
                id="daily_marathon",
                title="⚡️ Денний марафон",
                description="Надіслав 100+ повідомлень за один день",
                emoji="⚡️",
                sticker="⚡️",
                condition_type="daily_messages",
                condition_value=100,
                category="activity"
            ),
            Achievement(
                id="no_weekends",
                title="📆 Без вихідних",
                description="Активний 7+ днів поспіль",
                emoji="📆",
                sticker="📆",
                condition_type="consecutive_days",
                condition_value=7,
                category="activity"
            ),
            Achievement(
                id="chat_veteran",
                title="🎂 Чат-ветеран",
                description="Активний в чаті більше року",
                emoji="🎂",
                sticker="🎂",
                condition_type="days_active",
                condition_value=365,
                category="activity"
            ),
            Achievement(
                id="early_bird",
                title="☀️ Жайворонок",
                description="Надіслав перше повідомлення вранці",
                emoji="☀️",
                sticker="☀️",
                condition_type="first_morning_message",
                condition_value=1,
                category="activity"
            ),
            Achievement(
                id="night_owl",
                title="🌙 Сова",
                description="Надіслав останнє повідомлення вночі",
                emoji="🌙",
                sticker="🌙",
                condition_type="last_night_message",
                condition_value=1,
                category="activity"
            )
        ]
    
    @staticmethod
    def _get_media_achievements() -> List[Achievement]:
        """Get media and links achievements."""
        return [
            Achievement(
                id="photo_lover",
                title="📸 Фотолюбитель",
                description="Поділився 10+ фото",
                emoji="📸",
                sticker="📸",
                condition_type="photos_shared",
                condition_value=10,
                category="media"
            ),
            Achievement(
                id="photo_stream",
                title="🎞️ Фотопотік",
                description="Поділився 100+ фото",
                emoji="🎞️",
                sticker="🎞️",
                condition_type="photos_shared",
                condition_value=100,
                category="media"
            ),
            Achievement(
                id="twitter_user",
                title="🐦 Твітерський",
                description="Поділився 100+ посиланнями Twitter",
                emoji="🐦",
                sticker="🐦",
                condition_type="twitter_links",
                condition_value=100,
                category="media"
            ),
            Achievement(
                id="gamer",
                title="🎮 Гравець",
                description="Поділився 10+ посиланнями Steam",
                emoji="🎮",
                sticker="🎮",
                condition_type="steam_links",
                condition_value=10,
                category="media"
            ),
            Achievement(
                id="meme_lord",
                title="😂 Мемолог",
                description="Поділився 100+ мемами",
                emoji="😂",
                sticker="😂",
                condition_type="memes_shared",
                condition_value=100,
                category="media"
            ),
            Achievement(
                id="videographer",
                title="🎥 Відеограф",
                description="Завантажив своє перше відео",
                emoji="🎥",
                sticker="🎥",
                condition_type="videos_uploaded",
                condition_value=1,
                category="media"
            ),
            Achievement(
                id="chat_dj",
                title="🎶 Діджей чату",
                description="Поділився 10+ музичними треками",
                emoji="🎶",
                sticker="🎶",
                condition_type="music_shared",
                condition_value=10,
                category="media"
            )
        ]
    
    @staticmethod
    def _get_social_achievements() -> List[Achievement]:
        """Get social interaction achievements."""
        return [
            Achievement(
                id="soul_of_chat",
                title="🔥 Душа чату",
                description="Отримав 100+ реакцій",
                emoji="🔥",
                sticker="🔥",
                condition_type="reactions_received",
                condition_value=100,
                category="social"
            ),
            Achievement(
                id="commenter",
                title="↩️ Коментатор",
                description="Зробив свою першу відповідь",
                emoji="↩️",
                sticker="↩️",
                condition_type="replies_made",
                condition_value=1,
                category="social"
            ),
            Achievement(
                id="voice_of_people",
                title="📊 Голос народу",
                description="Створив своє перше опитування",
                emoji="📊",
                sticker="📊",
                condition_type="polls_created",
                condition_value=1,
                category="social"
            ),
            Achievement(
                id="emotional",
                title="😄 Емоційний",
                description="Надіслав свій перший емодзі",
                emoji="😄",
                sticker="😄",
                condition_type="emojis_sent",
                condition_value=1,
                category="social"
            ),
            Achievement(
                id="helpful",
                title="🤝 Helpful",
                description="Отримав 5+ подяк",
                emoji="🤝",
                sticker="🤝",
                condition_type="thanks_received",
                condition_value=5,
                category="social"
            ),
            Achievement(
                id="polite",
                title="🙏 Чемний",
                description="Отримав 100+ подяк",
                emoji="🙏",
                sticker="🙏",
                condition_type="thanks_received",
                condition_value=100,
                category="social"
            )
        ]
    
    @staticmethod
    def _get_rare_achievements() -> List[Achievement]:
        """Get rare/special achievements."""
        return [
            Achievement(
                id="novelist",
                title="📚 Романіст",
                description="Надіслав найдовше повідомлення в історії чату",
                emoji="📚",
                sticker="📚",
                condition_type="longest_message",
                condition_value=1,
                category="rare"
            ),
            Achievement(
                id="minimalist",
                title="👌 Мінімаліст",
                description="Надіслав найкоротше повідомлення ('ок')",
                emoji="👌",
                sticker="👌",
                condition_type="shortest_message",
                condition_value=1,
                category="rare"
            ),
            Achievement(
                id="laugher",
                title="🤣 Сміхун",
                description="Надіслав 100+ 'лол'/'ахаха' повідомлень",
                emoji="🤣",
                sticker="🤣",
                condition_type="laugh_messages",
                condition_value=100,
                category="rare"
            ),
            Achievement(
                id="tagger",
                title="📣 Тегер",
                description="Згадав інших користувачів 50+ разів",
                emoji="📣",
                sticker="📣",
                condition_type="mentions_made",
                condition_value=50,
                category="rare"
            ),
            Achievement(
                id="sticker_master",
                title="🖼️ Стікермайстер",
                description="Надіслав свій перший стікер",
                emoji="🖼️",
                sticker="🖼️",
                condition_type="stickers_sent",
                condition_value=1,
                category="rare"
            ),
            Achievement(
                id="solo_concert",
                title="🧑‍🎤 Сольний концерт",
                description="Надіслав 3+ повідомлення поспіль без відповідей",
                emoji="🧑‍🎤",
                sticker="🧑‍🎤",
                condition_type="consecutive_messages",
                condition_value=3,
                category="rare"
            ),
            Achievement(
                id="rebel",
                title="🤬 Бунтар",
                description="Надіслав своє перше лайливе слово",
                emoji="🤬",
                sticker="🤬",
                condition_type="swear_words",
                condition_value=1,
                category="rare"
            )
        ]
    
    @staticmethod
    def _get_level_achievements() -> List[Achievement]:
        """Get level-based achievements."""
        return [
            Achievement(
                id="level_up",
                title="🆙 Level Up!",
                description="Досяг 5-го рівня",
                emoji="🆙",
                sticker="🆙",
                condition_type="level",
                condition_value=5,
                category="level"
            )
        ]


class AchievementEngine:
    """
    Core achievement system engine.
    
    Handles achievement checking, unlocking logic, and condition evaluation
    for all achievement types in the system.
    """
    
    def __init__(self, achievement_repository: Optional[AchievementRepository] = None):
        """
        Initialize the achievement engine.
        
        Args:
            achievement_repository: Repository for achievement database operations
        """
        self.repository = achievement_repository or AchievementRepository()
        self._achievements_cache: Optional[List[Achievement]] = None
        self._achievements_by_id: Optional[Dict[str, Achievement]] = None
        
        # Initialize achievement definitions
        self._initialize_achievements()
    
    def _initialize_achievements(self) -> None:
        """Initialize achievement definitions in the database."""
        try:
            # This will be called during service initialization
            # to ensure all achievements are defined in the database
            pass
        except Exception as e:
            logger.error(f"Error initializing achievements: {e}")
    
    async def initialize_achievement_definitions(self) -> None:
        """
        Initialize all achievement definitions in the database.
        
        This method should be called during service startup to ensure
        all achievements are properly defined in the database.
        """
        try:
            achievements = AchievementDefinitions.get_all_achievements()
            
            for achievement in achievements:
                await self.repository.save_achievement(achievement)
            
            logger.info(f"Initialized {len(achievements)} achievement definitions")
            
            # Clear cache to force reload
            self._achievements_cache = None
            self._achievements_by_id = None
            
        except Exception as e:
            logger.error(f"Error initializing achievement definitions: {e}")
            raise
    
    async def get_all_achievements(self) -> List[Achievement]:
        """
        Get all achievement definitions with caching.
        
        Returns:
            List of all Achievement objects
        """
        if self._achievements_cache is None:
            self._achievements_cache = await self.repository.get_all_achievements()
            self._achievements_by_id = {ach.id: ach for ach in self._achievements_cache}
        
        return self._achievements_cache
    
    async def get_achievement_by_id(self, achievement_id: str) -> Optional[Achievement]:
        """
        Get achievement by ID with caching.
        
        Args:
            achievement_id: The achievement's ID
            
        Returns:
            Achievement object if found, None otherwise
        """
        if self._achievements_by_id is None:
            await self.get_all_achievements()
        
        return self._achievements_by_id.get(achievement_id)
    
    async def check_achievements(
        self,
        user_id: UserId,
        chat_id: ChatId,
        user_stats: UserStats,
        context_data: Optional[Dict[str, Any]] = None
    ) -> List[Achievement]:
        """
        Check which achievements should be unlocked for a user.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            user_stats: Current user statistics
            context_data: Additional context data for complex conditions
            
        Returns:
            List of achievements that should be unlocked
        """
        try:
            # Get all achievements
            all_achievements = await self.get_all_achievements()
            
            # Get user's current achievements
            user_achievements = await self.repository.get_user_achievements(user_id, chat_id)
            unlocked_achievement_ids = {ua.achievement_id for ua in user_achievements}
            
            # Check each achievement
            new_achievements = []
            context_data = context_data or {}
            
            for achievement in all_achievements:
                # Skip if already unlocked
                if achievement.id in unlocked_achievement_ids:
                    continue
                
                # Check if condition is met
                if achievement.check_condition(user_stats, **context_data):
                    new_achievements.append(achievement)
            
            return new_achievements
            
        except Exception as e:
            logger.error(f"Error checking achievements for user {user_id}: {e}")
            return []
    
    async def unlock_achievement(
        self,
        user_id: UserId,
        chat_id: ChatId,
        achievement: Achievement
    ) -> UserAchievement:
        """
        Unlock a specific achievement for a user.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            achievement: The achievement to unlock
            
        Returns:
            UserAchievement object representing the unlocked achievement
        """
        try:
            # Check if already unlocked
            if await self.repository.has_achievement(user_id, chat_id, achievement.id):
                logger.debug(f"Achievement {achievement.id} already unlocked for user {user_id}")
                return UserAchievement(user_id, chat_id, achievement.id)
            
            # Create user achievement record
            user_achievement = UserAchievement(
                user_id=user_id,
                chat_id=chat_id,
                achievement_id=achievement.id,
                unlocked_at=datetime.utcnow()
            )
            
            # Save to database
            await self.repository.unlock_achievement(user_achievement)
            
            logger.info(f"Unlocked achievement '{achievement.title}' for user {user_id} in chat {chat_id}")
            return user_achievement
            
        except Exception as e:
            logger.error(f"Error unlocking achievement {achievement.id} for user {user_id}: {e}")
            raise
    
    async def unlock_achievements(
        self,
        user_id: UserId,
        chat_id: ChatId,
        achievements: List[Achievement]
    ) -> List[UserAchievement]:
        """
        Unlock multiple achievements for a user.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            achievements: List of achievements to unlock
            
        Returns:
            List of UserAchievement objects representing unlocked achievements
        """
        if not achievements:
            return []
        
        try:
            user_achievements = []
            
            for achievement in achievements:
                # Check if already unlocked
                if await self.repository.has_achievement(user_id, chat_id, achievement.id):
                    continue
                
                user_achievement = UserAchievement(
                    user_id=user_id,
                    chat_id=chat_id,
                    achievement_id=achievement.id,
                    unlocked_at=datetime.utcnow()
                )
                user_achievements.append(user_achievement)
            
            # Bulk unlock
            if user_achievements:
                await self.repository.bulk_unlock_achievements(user_achievements)
                
                achievement_titles = [ach.title for ach in achievements if any(ua.achievement_id == ach.id for ua in user_achievements)]
                logger.info(f"Unlocked {len(user_achievements)} achievements for user {user_id}: {', '.join(achievement_titles)}")
            
            return user_achievements
            
        except Exception as e:
            logger.error(f"Error unlocking multiple achievements for user {user_id}: {e}")
            return []
    
    async def is_achievement_unlocked(
        self,
        user_id: UserId,
        chat_id: ChatId,
        achievement_id: str
    ) -> bool:
        """
        Check if a user has unlocked a specific achievement.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            achievement_id: The achievement's ID
            
        Returns:
            True if the achievement is unlocked, False otherwise
        """
        try:
            return await self.repository.has_achievement(user_id, chat_id, achievement_id)
        except Exception as e:
            logger.error(f"Error checking if achievement {achievement_id} is unlocked for user {user_id}: {e}")
            return False
    
    async def get_user_achievements(
        self,
        user_id: UserId,
        chat_id: ChatId
    ) -> List[Achievement]:
        """
        Get all achievements unlocked by a user.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            
        Returns:
            List of Achievement objects unlocked by the user
        """
        try:
            achievement_data = await self.repository.get_user_achievements_with_details(user_id, chat_id)
            return [achievement for _, achievement in achievement_data]
        except Exception as e:
            logger.error(f"Error getting user achievements for user {user_id}: {e}")
            return []
    
    async def get_achievements_by_category(self, category: str) -> List[Achievement]:
        """
        Get achievements by category.
        
        Args:
            category: The achievement category
            
        Returns:
            List of Achievement objects in the specified category
        """
        try:
            return await self.repository.get_achievements_by_category(category)
        except Exception as e:
            logger.error(f"Error getting achievements by category {category}: {e}")
            return []
    
    def create_context_data(
        self,
        message_text: str = "",
        is_photo: bool = False,
        is_video: bool = False,
        is_sticker: bool = False,
        is_reply: bool = False,
        is_poll: bool = False,
        has_emoji: bool = False,
        mentions_count: int = 0,
        daily_messages: int = 0,
        consecutive_days: int = 0,
        days_active: int = 0,
        is_first_morning_message: bool = False,
        is_last_night_message: bool = False,
        reactions_received: int = 0,
        consecutive_messages: int = 0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create context data for achievement checking.
        
        This method helps create the context data dictionary needed for
        complex achievement conditions that require additional information
        beyond basic user statistics.
        
        Args:
            message_text: The message text for content analysis
            is_photo: Whether the message contains a photo
            is_video: Whether the message contains a video
            is_sticker: Whether the message is a sticker
            is_reply: Whether the message is a reply
            is_poll: Whether the message is a poll
            has_emoji: Whether the message contains emojis
            mentions_count: Number of user mentions in the message
            daily_messages: Number of messages sent today
            consecutive_days: Number of consecutive active days
            days_active: Total days the user has been active
            is_first_morning_message: Whether this is the first message of the morning
            is_last_night_message: Whether this is the last message of the night
            reactions_received: Number of reactions received
            consecutive_messages: Number of consecutive messages without replies
            **kwargs: Additional context data
            
        Returns:
            Dictionary with context data for achievement checking
        """
        context = {
            'daily_messages': daily_messages,
            'consecutive_days': consecutive_days,
            'days_active': days_active,
            'is_first_morning_message': is_first_morning_message,
            'is_last_night_message': is_last_night_message,
            'reactions_received': reactions_received,
            'consecutive_messages': consecutive_messages,
            'mentions_made': mentions_count,
            **kwargs
        }
        
        # Analyze message content
        if message_text:
            context.update(self._analyze_message_content(message_text))
        
        # Media type detection
        if is_photo:
            context['photos_shared'] = context.get('photos_shared', 0) + 1
        if is_video:
            context['videos_uploaded'] = context.get('videos_uploaded', 0) + 1
        if is_sticker:
            context['stickers_sent'] = context.get('stickers_sent', 0) + 1
        if is_reply:
            context['replies_made'] = context.get('replies_made', 0) + 1
        if is_poll:
            context['polls_created'] = context.get('polls_created', 0) + 1
        if has_emoji:
            context['emojis_sent'] = context.get('emojis_sent', 0) + 1
        
        return context
    
    def _analyze_message_content(self, message_text: str) -> Dict[str, Any]:
        """
        Analyze message content for achievement conditions.
        
        Args:
            message_text: The message text to analyze
            
        Returns:
            Dictionary with analysis results
        """
        analysis = {}
        
        if not message_text:
            return analysis
        
        text_lower = message_text.lower()
        
        # Check for laugh expressions
        laugh_patterns = [
            r'\b(лол|lol|ахаха|ahaha|хаха|haha|ахах|ahah)\b',
            r'😂+',
            r'🤣+',
            r'(ха){3,}',  # хахаха, хахахаха, etc.
        ]
        
        laugh_count = 0
        for pattern in laugh_patterns:
            matches = re.findall(pattern, message_text, re.IGNORECASE)  # Use original message_text for emoji detection
            laugh_count += len(matches)
        
        if laugh_count > 0:
            analysis['laugh_messages'] = 1
        
        # Check for shortest message (exactly "ок" or "ok")
        if text_lower.strip() in ['ок', 'ok']:
            analysis['is_shortest_message'] = True
        
        # Check message length for longest message detection
        # This would typically be compared against chat history
        analysis['message_length'] = len(message_text)
        
        # Check for Twitter links
        twitter_patterns = [
            r'twitter\.com',
            r'x\.com',
            r't\.co'
        ]
        
        twitter_count = 0
        for pattern in twitter_patterns:
            matches = re.findall(pattern, text_lower)
            twitter_count += len(matches)
        
        if twitter_count > 0:
            analysis['twitter_links'] = twitter_count
        
        # Check for Steam links
        steam_patterns = [
            r'store\.steampowered\.com',
            r'steamcommunity\.com'
        ]
        
        steam_count = 0
        for pattern in steam_patterns:
            matches = re.findall(pattern, text_lower)
            steam_count += len(matches)
        
        if steam_count > 0:
            analysis['steam_links'] = steam_count
        
        # Check for swear words (basic detection)
        # This is a simplified implementation - in production you'd want a more sophisticated approach
        swear_patterns = [
            r'\b(блять|сука|хуй|пизда|ебать|fuck|shit|damn|пізда|їбать|блядь|сука)\b'
        ]
        
        swear_count = 0
        for pattern in swear_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            swear_count += len(matches)
        
        if swear_count > 0:
            analysis['swear_words'] = 1
        
        # Check for meme indicators (simplified)
        meme_patterns = [
            r'мем',
            r'meme',
            r'кек',
            r'kek',
            r'топ',
            r'based'
        ]
        
        meme_count = 0
        for pattern in meme_patterns:
            matches = re.findall(pattern, text_lower)
            meme_count += len(matches)
        
        if meme_count > 0:
            analysis['memes_shared'] = 1
        
        return analysis
    
    async def get_achievement_progress(
        self,
        user_id: UserId,
        chat_id: ChatId,
        user_stats: UserStats,
        achievement_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get progress towards a specific achievement.
        
        Args:
            user_id: The user's ID
            chat_id: The chat's ID
            user_stats: Current user statistics
            achievement_id: The achievement's ID
            
        Returns:
            Dictionary with progress information or None if achievement not found
        """
        try:
            achievement = await self.get_achievement_by_id(achievement_id)
            if not achievement:
                return None
            
            # Check if already unlocked
            is_unlocked = await self.is_achievement_unlocked(user_id, chat_id, achievement_id)
            
            if is_unlocked:
                return {
                    'achievement': achievement.to_dict(),
                    'progress': achievement.condition_value,
                    'target': achievement.condition_value,
                    'percentage': 100.0,
                    'unlocked': True
                }
            
            # Calculate current progress
            current_value = self._get_current_value_for_condition(user_stats, achievement.condition_type)
            percentage = min(100.0, (current_value / achievement.condition_value) * 100) if achievement.condition_value > 0 else 0.0
            
            return {
                'achievement': achievement.to_dict(),
                'progress': current_value,
                'target': achievement.condition_value,
                'percentage': percentage,
                'unlocked': False
            }
            
        except Exception as e:
            logger.error(f"Error getting achievement progress for {achievement_id}: {e}")
            return None
    
    def _get_current_value_for_condition(self, user_stats: UserStats, condition_type: str) -> int:
        """
        Get the current value for a specific condition type.
        
        Args:
            user_stats: User statistics
            condition_type: The condition type to check
            
        Returns:
            Current value for the condition
        """
        if condition_type == "messages_count":
            return user_stats.messages_count
        elif condition_type == "links_shared":
            return user_stats.links_shared
        elif condition_type == "thanks_received":
            return user_stats.thanks_received
        elif condition_type == "level":
            return user_stats.level
        elif condition_type == "xp":
            return user_stats.xp
        else:
            # For complex conditions, we can't determine current value without context
            return 0