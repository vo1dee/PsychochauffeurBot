"""
Notification service for the user leveling system.

This module handles all notification formatting and delivery for level-ups,
achievement unlocks, and other leveling-related events.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import random

from telegram import Update, Message, User
from telegram.ext import ContextTypes

from modules.leveling_models import Achievement, LevelUpResult, UserStats
from modules.types import UserId, ChatId

logger = logging.getLogger(__name__)


class LevelingNotificationService:
    """
    Service for handling leveling system notifications.
    
    This service provides formatted messages for level-ups, achievement unlocks,
    and other leveling events with proper emoji usage and user mentions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the notification service.
        
        Args:
            config: Configuration dictionary for notification settings
        """
        self.config = config or {}
        self._enabled = self.config.get('enabled', True)
        self._use_emojis = self.config.get('use_emojis', True)
        self._use_mentions = self.config.get('use_mentions', True)
        self._celebration_style = self.config.get('celebration_style', 'enthusiastic')
        
        # Celebration emojis for different events
        self._level_up_emojis = [
            "🎉", "🎊", "✨", "🌟", "⭐", "🎈", "🎁", "🏆", "👑", "🔥"
        ]
        
        self._achievement_emojis = [
            "🏆", "🥇", "🎖️", "🏅", "⭐", "🌟", "✨", "💫", "🎯", "🎪"
        ]
        
        # Level milestone emojis
        self._level_milestone_emojis = {
            5: "🆙",
            10: "🔟",
            15: "🎯",
            20: "🌟",
            25: "🎊",
            30: "👑",
            50: "🏆",
            75: "💎",
            100: "🌌"
        }
        
        logger.info("LevelingNotificationService initialized")
    
    async def send_level_up_notification(
        self,
        level_up_result: LevelUpResult,
        user: User,
        original_message: Message,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Send a level-up celebration message.
        
        Args:
            level_up_result: Level up information
            user: Telegram user who leveled up
            original_message: Original message that triggered the level up
            context: Bot context
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self._enabled:
            return False
        
        try:
            message_text = self._format_level_up_message(level_up_result, user)
            
            await original_message.reply_text(
                message_text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            logger.info(f"Sent level up notification for user {user.id} (Level {level_up_result.new_level})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send level up notification: {e}", exc_info=True)
            return False
    
    async def send_achievement_notification(
        self,
        achievement: Achievement,
        user: User,
        original_message: Message,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Send an achievement unlock celebration message.
        
        Args:
            achievement: Unlocked achievement
            user: Telegram user who unlocked the achievement
            original_message: Original message that triggered the achievement
            context: Bot context
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self._enabled:
            return False
        
        try:
            message_text = self._format_achievement_message(achievement, user)
            
            await original_message.reply_text(
                message_text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            logger.info(f"Sent achievement notification for user {user.id} ({achievement.id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send achievement notification: {e}", exc_info=True)
            return False
    
    async def send_multiple_achievements_notification(
        self,
        achievements: List[Achievement],
        user: User,
        original_message: Message,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Send a notification for multiple achievements unlocked at once.
        
        Args:
            achievements: List of unlocked achievements
            user: Telegram user who unlocked the achievements
            original_message: Original message that triggered the achievements
            context: Bot context
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self._enabled or not achievements:
            return False
        
        try:
            if len(achievements) == 1:
                return await self.send_achievement_notification(
                    achievements[0], user, original_message, context
                )
            
            message_text = self._format_multiple_achievements_message(achievements, user)
            
            await original_message.reply_text(
                message_text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            logger.info(f"Sent multiple achievements notification for user {user.id} ({len(achievements)} achievements)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send multiple achievements notification: {e}", exc_info=True)
            return False
    
    def _format_level_up_message(self, level_up_result: LevelUpResult, user: User) -> str:
        """
        Format a level-up celebration message.
        
        Args:
            level_up_result: Level up information
            user: Telegram user who leveled up
            
        Returns:
            Formatted message text
        """
        username = self._get_user_display_name(user)
        user_mention = self._get_user_mention(user) if self._use_mentions else username
        
        # Get celebration emojis
        celebration_emoji = self._get_random_emoji(self._level_up_emojis) if self._use_emojis else ""
        milestone_emoji = self._get_milestone_emoji(level_up_result.new_level)
        
        # Build message based on celebration style
        if self._celebration_style == 'minimal':
            return (
                f"{celebration_emoji} {user_mention} reached Level {level_up_result.new_level}! "
                f"{milestone_emoji}\n"
                f"Total XP: {level_up_result.total_xp}\n"
                f"Use /profile to see your progress!"
            )
        elif self._celebration_style == 'enthusiastic':
            xp_emoji = "✨ " if self._use_emojis else ""
            progress_emoji = "📊 " if self._use_emojis else ""
            profile_emoji = "🎯 " if self._use_emojis else ""
            
            return (
                f"{celebration_emoji} <b>Congratulations {user_mention}!</b> {celebration_emoji}\n"
                f"{milestone_emoji} You've reached <b>Level {level_up_result.new_level}</b>! {milestone_emoji}\n"
                f"{xp_emoji}Total XP: <b>{level_up_result.total_xp}</b>\n"
                f"{progress_emoji}Level progress: {level_up_result.old_level} → {level_up_result.new_level}\n\n"
                f"{profile_emoji}Use /profile to see your stats and achievements!"
            )
        else:  # balanced
            return (
                f"{celebration_emoji} Congratulations {user_mention}!\n"
                f"You've reached Level {level_up_result.new_level}! {milestone_emoji}\n"
                f"Total XP: {level_up_result.total_xp}\n\n"
                f"Use /profile to see your stats and achievements!"
            )
    
    def _format_achievement_message(self, achievement: Achievement, user: User) -> str:
        """
        Format an achievement unlock celebration message.
        
        Args:
            achievement: Unlocked achievement
            user: Telegram user who unlocked the achievement
            
        Returns:
            Formatted message text
        """
        username = self._get_user_display_name(user)
        user_mention = self._get_user_mention(user) if self._use_mentions else username
        
        # Get celebration emojis
        celebration_emoji = self._get_random_emoji(self._achievement_emojis) if self._use_emojis else ""
        achievement_emoji = achievement.emoji if self._use_emojis else ""
        
        # Build message based on celebration style
        if self._celebration_style == 'minimal':
            return (
                f"{celebration_emoji} Achievement Unlocked!\n"
                f"{user_mention} earned: {achievement_emoji} {achievement.title}"
            )
        elif self._celebration_style == 'enthusiastic':
            party_emoji = "🎊 " if self._use_emojis else ""
            desc_emoji = "📝 " if self._use_emojis else ""
            category_emoji = "🏷️ " if self._use_emojis else ""
            
            return (
                f"{celebration_emoji} <b>Achievement Unlocked!</b> {celebration_emoji}\n"
                f"{party_emoji}{user_mention} earned: {achievement_emoji} <b>{achievement.title}</b>\n"
                f"{desc_emoji}{achievement.description}\n"
                f"{category_emoji}Category: {achievement.category.title()}"
            )
        else:  # balanced
            return (
                f"{celebration_emoji} Achievement Unlocked! {celebration_emoji}\n"
                f"{user_mention} earned: {achievement_emoji} <b>{achievement.title}</b>\n"
                f"{achievement.description}"
            )
    
    def _format_multiple_achievements_message(self, achievements: List[Achievement], user: User) -> str:
        """
        Format a message for multiple achievements unlocked at once.
        
        Args:
            achievements: List of unlocked achievements
            user: Telegram user who unlocked the achievements
            
        Returns:
            Formatted message text
        """
        username = self._get_user_display_name(user)
        user_mention = self._get_user_mention(user) if self._use_mentions else username
        
        # Get celebration emojis
        celebration_emoji = self._get_random_emoji(self._achievement_emojis) if self._use_emojis else ""
        
        # Build achievements list
        achievements_text = []
        for achievement in achievements:
            emoji = achievement.emoji if self._use_emojis else ""
            achievements_text.append(f"• {emoji} <b>{achievement.title}</b>")
        
        achievements_list = "\n".join(achievements_text)
        
        # Build message based on celebration style
        if self._celebration_style == 'minimal':
            return (
                f"{celebration_emoji} Multiple Achievements Unlocked!\n"
                f"{user_mention} earned {len(achievements)} achievements:\n\n"
                f"{achievements_list}"
            )
        elif self._celebration_style == 'enthusiastic':
            party_emoji = "🎊 " if self._use_emojis else ""
            party_emoji_end = " 🎊" if self._use_emojis else ""
            profile_emoji = "🎯 " if self._use_emojis else ""
            
            return (
                f"{celebration_emoji} <b>Multiple Achievements Unlocked!</b> {celebration_emoji}\n"
                f"{party_emoji}{user_mention} earned <b>{len(achievements)} achievements</b> at once!{party_emoji_end}\n\n"
                f"{achievements_list}\n\n"
                f"{profile_emoji}Use /profile to see all your achievements!"
            )
        else:  # balanced
            return (
                f"{celebration_emoji} Multiple Achievements Unlocked! {celebration_emoji}\n"
                f"{user_mention} earned <b>{len(achievements)} achievements</b>:\n\n"
                f"{achievements_list}\n\n"
                f"Use /profile to see your complete collection!"
            )
    
    def _get_user_display_name(self, user: User) -> str:
        """
        Get a display name for the user.
        
        Args:
            user: Telegram user
            
        Returns:
            User display name
        """
        if user.username:
            return f"@{user.username}"
        elif user.first_name:
            return user.first_name
        else:
            return f"User {user.id}"
    
    def _get_user_mention(self, user: User) -> str:
        """
        Get a user mention for the user.
        
        Args:
            user: Telegram user
            
        Returns:
            User mention in HTML format
        """
        display_name = user.first_name or user.username or f"User {user.id}"
        return f'<a href="tg://user?id={user.id}">{display_name}</a>'
    
    def _get_random_emoji(self, emoji_list: List[str]) -> str:
        """
        Get a random emoji from the provided list.
        
        Args:
            emoji_list: List of emojis to choose from
            
        Returns:
            Random emoji from the list
        """
        if not emoji_list or not self._use_emojis:
            return ""
        return random.choice(emoji_list)
    
    def _get_milestone_emoji(self, level: int) -> str:
        """
        Get a milestone emoji for special levels.
        
        Args:
            level: User level
            
        Returns:
            Milestone emoji if applicable, empty string otherwise
        """
        if not self._use_emojis:
            return ""
        
        return self._level_milestone_emojis.get(level, "")
    
    def format_profile_prompt_message(self, user: User) -> str:
        """
        Format a message prompting the user to check their profile.
        
        Args:
            user: Telegram user
            
        Returns:
            Formatted prompt message
        """
        user_mention = self._get_user_mention(user) if self._use_mentions else self._get_user_display_name(user)
        
        if self._use_emojis:
            return f"🎯 {user_mention}, use /profile to see your complete stats and achievements!"
        else:
            return f"{user_mention}, use /profile to see your complete stats and achievements!"
    
    def is_enabled(self) -> bool:
        """
        Check if notifications are enabled.
        
        Returns:
            True if notifications are enabled
        """
        return self._enabled
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update notification configuration.
        
        Args:
            config: New configuration dictionary
        """
        self.config.update(config)
        self._enabled = self.config.get('enabled', True)
        self._use_emojis = self.config.get('use_emojis', True)
        self._use_mentions = self.config.get('use_mentions', True)
        self._celebration_style = self.config.get('celebration_style', 'enthusiastic')
        
        logger.info(f"Updated notification configuration: enabled={self._enabled}")