"""
Comprehensive tests for the leveling notification service.

This module tests notification formatting, delivery, and configuration
for level-ups, achievement unlocks, and other leveling events.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from telegram import User, Message, Chat
from telegram.ext import ContextTypes

from modules.leveling_notification_service import LevelingNotificationService
from modules.leveling_models import Achievement, LevelUpResult


class TestLevelingNotificationService:
    """Comprehensive tests for leveling notification functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            'enabled': True,
            'use_emojis': True,
            'use_mentions': True,
            'celebration_style': 'enthusiastic'
        }
        self.service = LevelingNotificationService(self.config)
        
        # Mock user
        self.user = Mock(spec=User)
        self.user.id = 123456
        self.user.username = "testuser"
        self.user.first_name = "Test"
        self.user.last_name = "User"
        self.user.is_bot = False
        
        # Mock message
        self.message = Mock(spec=Message)
        self.message.from_user = self.user
        self.message.chat = Mock(spec=Chat)
        self.message.chat.id = -100123456
        self.message.chat.type = 'supergroup'
        self.message.reply_text = AsyncMock()
        
        # Mock context
        self.context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    def test_initialization_default_config(self):
        """Test service initialization with default configuration."""
        service = LevelingNotificationService()
        
        assert service.is_enabled() is True
        assert service._use_emojis is True
        assert service._use_mentions is True
        assert service._celebration_style == 'enthusiastic'
    
    def test_initialization_custom_config(self):
        """Test service initialization with custom configuration."""
        config = {
            'enabled': False,
            'use_emojis': False,
            'use_mentions': False,
            'celebration_style': 'minimal'
        }
        service = LevelingNotificationService(config)
        
        assert service.is_enabled() is False
        assert service._use_emojis is False
        assert service._use_mentions is False
        assert service._celebration_style == 'minimal'
    
    @pytest.mark.asyncio
    async def test_send_level_up_notification_success(self):
        """Test successful level up notification delivery."""
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=4,
            new_level=5,
            total_xp=400
        )
        
        result = await self.service.send_level_up_notification(
            level_up_result, self.user, self.message, self.context
        )
        
        assert result is True
        self.message.reply_text.assert_called_once()
        
        # Check message content
        call_args = self.message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "Congratulations" in message_text
        assert "Level 5" in message_text
        assert "400" in message_text  # Total XP
        assert "/profile" in message_text
        assert "🆙" in message_text  # Level 5 milestone emoji
    
    @pytest.mark.asyncio
    async def test_send_level_up_notification_disabled(self):
        """Test level up notification when service is disabled."""
        self.service._enabled = False
        
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=4,
            new_level=5,
            total_xp=400
        )
        
        result = await self.service.send_level_up_notification(
            level_up_result, self.user, self.message, self.context
        )
        
        assert result is False
        self.message.reply_text.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_achievement_notification_success(self):
        """Test successful achievement notification delivery."""
        achievement = Achievement(
            id="chatterbox",
            title="Chatterbox",
            description="Send 100+ messages",
            emoji="💬",
            sticker="💬",
            condition_type="messages_count",
            condition_value=100,
            category="activity"
        )
        
        result = await self.service.send_achievement_notification(
            achievement, self.user, self.message, self.context
        )
        
        assert result is True
        self.message.reply_text.assert_called_once()
        
        # Check message content
        call_args = self.message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "Achievement Unlocked" in message_text
        assert "Chatterbox" in message_text
        assert "💬" in message_text
        assert "Send 100+ messages" in message_text
    
    @pytest.mark.asyncio
    async def test_send_multiple_achievements_notification(self):
        """Test notification for multiple achievements unlocked at once."""
        achievements = [
            Achievement(
                id="chatterbox",
                title="Chatterbox",
                description="Send 100+ messages",
                emoji="💬",
                sticker="💬",
                condition_type="messages_count",
                condition_value=100,
                category="activity"
            ),
            Achievement(
                id="helpful",
                title="Helpful",
                description="Receive 5+ thanks",
                emoji="🤝",
                sticker="🤝",
                condition_type="thanks_received",
                condition_value=5,
                category="social"
            )
        ]
        
        result = await self.service.send_multiple_achievements_notification(
            achievements, self.user, self.message, self.context
        )
        
        assert result is True
        self.message.reply_text.assert_called_once()
        
        # Check message content
        call_args = self.message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "Multiple Achievements Unlocked" in message_text
        assert "2 achievements" in message_text
        assert "Chatterbox" in message_text
        assert "Helpful" in message_text
        assert "💬" in message_text
        assert "🤝" in message_text
    
    @pytest.mark.asyncio
    async def test_send_single_achievement_in_multiple_list(self):
        """Test that single achievement in list uses single achievement method."""
        achievement = Achievement(
            id="chatterbox",
            title="Chatterbox",
            description="Send 100+ messages",
            emoji="💬",
            sticker="💬",
            condition_type="messages_count",
            condition_value=100,
            category="activity"
        )
        
        with patch.object(self.service, 'send_achievement_notification', return_value=True) as mock_single:
            result = await self.service.send_multiple_achievements_notification(
                [achievement], self.user, self.message, self.context
            )
            
            assert result is True
            mock_single.assert_called_once_with(achievement, self.user, self.message, self.context)
    
    def test_format_level_up_message_enthusiastic(self):
        """Test level up message formatting with enthusiastic style."""
        self.service._celebration_style = 'enthusiastic'
        
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=4,
            new_level=5,
            total_xp=400
        )
        
        message = self.service._format_level_up_message(level_up_result, self.user)
        
        assert "<b>Congratulations" in message
        assert "<b>Level 5</b>" in message
        assert "<b>400</b>" in message
        assert "4 → 5" in message
        assert "🆙" in message  # Level 5 milestone
        assert "/profile" in message
    
    def test_format_level_up_message_minimal(self):
        """Test level up message formatting with minimal style."""
        self.service._celebration_style = 'minimal'
        
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=9,
            new_level=10,
            total_xp=1000
        )
        
        message = self.service._format_level_up_message(level_up_result, self.user)
        
        assert "reached Level 10" in message
        assert "Total XP: 1000" in message
        assert "🔟" in message  # Level 10 milestone
        assert "/profile" in message
        # Should not have HTML formatting in minimal style
        assert "<b>" not in message
    
    def test_format_level_up_message_balanced(self):
        """Test level up message formatting with balanced style."""
        self.service._celebration_style = 'balanced'
        
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=19,
            new_level=20,
            total_xp=5000
        )
        
        message = self.service._format_level_up_message(level_up_result, self.user)
        
        assert "Congratulations" in message
        assert "Level 20" in message
        assert "Total XP: 5000" in message
        assert "🌟" in message  # Level 20 milestone
        assert "/profile" in message
    
    def test_format_achievement_message_enthusiastic(self):
        """Test achievement message formatting with enthusiastic style."""
        self.service._celebration_style = 'enthusiastic'
        
        achievement = Achievement(
            id="chatterbox",
            title="Chatterbox",
            description="Send 100+ messages",
            emoji="💬",
            sticker="💬",
            condition_type="messages_count",
            condition_value=100,
            category="activity"
        )
        
        message = self.service._format_achievement_message(achievement, self.user)
        
        assert "<b>Achievement Unlocked!</b>" in message
        assert "<b>Chatterbox</b>" in message
        assert "Send 100+ messages" in message
        assert "Category: Activity" in message
        assert "💬" in message
    
    def test_format_achievement_message_minimal(self):
        """Test achievement message formatting with minimal style."""
        self.service._celebration_style = 'minimal'
        
        achievement = Achievement(
            id="helpful",
            title="Helpful",
            description="Receive 5+ thanks",
            emoji="🤝",
            sticker="🤝",
            condition_type="thanks_received",
            condition_value=5,
            category="social"
        )
        
        message = self.service._format_achievement_message(achievement, self.user)
        
        assert "Achievement Unlocked!" in message
        assert "Helpful" in message
        assert "🤝" in message
        # Should not have HTML formatting or description in minimal style
        assert "<b>" not in message
        assert "Receive 5+ thanks" not in message
    
    def test_get_user_display_name_with_username(self):
        """Test user display name generation with username."""
        user = Mock(spec=User)
        user.username = "testuser"
        user.first_name = "Test"
        user.id = 123456
        
        display_name = self.service._get_user_display_name(user)
        assert display_name == "@testuser"
    
    def test_get_user_display_name_without_username(self):
        """Test user display name generation without username."""
        user = Mock(spec=User)
        user.username = None
        user.first_name = "Test"
        user.id = 123456
        
        display_name = self.service._get_user_display_name(user)
        assert display_name == "Test"
    
    def test_get_user_display_name_fallback(self):
        """Test user display name generation fallback."""
        user = Mock(spec=User)
        user.username = None
        user.first_name = None
        user.id = 123456
        
        display_name = self.service._get_user_display_name(user)
        assert display_name == "User 123456"
    
    def test_get_user_mention(self):
        """Test user mention generation."""
        user = Mock(spec=User)
        user.id = 123456
        user.first_name = "Test"
        user.username = "testuser"
        
        mention = self.service._get_user_mention(user)
        assert mention == '<a href="tg://user?id=123456">Test</a>'
    
    def test_get_user_mention_fallback(self):
        """Test user mention generation with fallback."""
        user = Mock(spec=User)
        user.id = 123456
        user.first_name = None
        user.username = "testuser"
        
        mention = self.service._get_user_mention(user)
        assert mention == '<a href="tg://user?id=123456">testuser</a>'
    
    def test_get_milestone_emoji(self):
        """Test milestone emoji selection."""
        # Test specific milestones
        assert self.service._get_milestone_emoji(5) == "🆙"
        assert self.service._get_milestone_emoji(10) == "🔟"
        assert self.service._get_milestone_emoji(20) == "🌟"
        assert self.service._get_milestone_emoji(50) == "🏆"
        assert self.service._get_milestone_emoji(100) == "🌌"
        
        # Test non-milestone level
        assert self.service._get_milestone_emoji(7) == ""
    
    def test_get_milestone_emoji_disabled(self):
        """Test milestone emoji when emojis are disabled."""
        self.service._use_emojis = False
        
        assert self.service._get_milestone_emoji(5) == ""
        assert self.service._get_milestone_emoji(10) == ""
    
    def test_get_random_emoji(self):
        """Test random emoji selection."""
        emoji_list = ["🎉", "🎊", "✨"]
        
        # Test multiple calls to ensure randomness works
        emojis = [self.service._get_random_emoji(emoji_list) for _ in range(10)]
        
        # All emojis should be from the list
        for emoji in emojis:
            assert emoji in emoji_list
        
        # Should have some variation (not all the same)
        assert len(set(emojis)) > 1 or len(emoji_list) == 1
    
    def test_get_random_emoji_disabled(self):
        """Test random emoji when emojis are disabled."""
        self.service._use_emojis = False
        emoji_list = ["🎉", "🎊", "✨"]
        
        result = self.service._get_random_emoji(emoji_list)
        assert result == ""
    
    def test_get_random_emoji_empty_list(self):
        """Test random emoji with empty list."""
        result = self.service._get_random_emoji([])
        assert result == ""
    
    def test_format_profile_prompt_message(self):
        """Test profile prompt message formatting."""
        message = self.service.format_profile_prompt_message(self.user)
        
        assert "/profile" in message
        assert "stats and achievements" in message
        assert "🎯" in message
    
    def test_format_profile_prompt_message_no_emojis(self):
        """Test profile prompt message without emojis."""
        self.service._use_emojis = False
        
        message = self.service.format_profile_prompt_message(self.user)
        
        assert "/profile" in message
        assert "stats and achievements" in message
        assert "🎯" not in message
    
    def test_update_config(self):
        """Test configuration updates."""
        new_config = {
            'enabled': False,
            'use_emojis': False,
            'celebration_style': 'minimal'
        }
        
        self.service.update_config(new_config)
        
        assert self.service.is_enabled() is False
        assert self.service._use_emojis is False
        assert self.service._celebration_style == 'minimal'
        # use_mentions should remain unchanged
        assert self.service._use_mentions is True
    
    @pytest.mark.asyncio
    async def test_notification_error_handling(self):
        """Test error handling in notification delivery."""
        # Mock reply_text to raise an exception
        self.message.reply_text.side_effect = Exception("Network error")
        
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=4,
            new_level=5,
            total_xp=400
        )
        
        result = await self.service.send_level_up_notification(
            level_up_result, self.user, self.message, self.context
        )
        
        # Should return False on error but not raise exception
        assert result is False
        self.message.reply_text.assert_called_once()
    
    def test_message_formatting_without_mentions(self):
        """Test message formatting when mentions are disabled."""
        self.service._use_mentions = False
        
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=4,
            new_level=5,
            total_xp=400
        )
        
        message = self.service._format_level_up_message(level_up_result, self.user)
        
        # Should use display name instead of mention
        assert "@testuser" in message
        assert '<a href="tg://user?id=' not in message
    
    def test_message_formatting_without_emojis(self):
        """Test message formatting when emojis are disabled."""
        self.service._use_emojis = False
        
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=4,
            new_level=5,
            total_xp=400
        )
        
        message = self.service._format_level_up_message(level_up_result, self.user)
        
        # Should not contain emojis
        assert "🎉" not in message
        assert "🆙" not in message
        assert "✨" not in message
    
    @pytest.mark.asyncio
    async def test_empty_achievements_list(self):
        """Test handling of empty achievements list."""
        result = await self.service.send_multiple_achievements_notification(
            [], self.user, self.message, self.context
        )
        
        assert result is False
        self.message.reply_text.assert_not_called()
    
    def test_format_multiple_achievements_message_balanced(self):
        """Test multiple achievements message formatting with balanced style."""
        self.service._celebration_style = 'balanced'
        
        achievements = [
            Achievement(
                id="chatterbox",
                title="Chatterbox",
                description="Send 100+ messages",
                emoji="💬",
                sticker="💬",
                condition_type="messages_count",
                condition_value=100,
                category="activity"
            ),
            Achievement(
                id="helpful",
                title="Helpful",
                description="Receive 5+ thanks",
                emoji="🤝",
                sticker="🤝",
                condition_type="thanks_received",
                condition_value=5,
                category="social"
            )
        ]
        
        message = self.service._format_multiple_achievements_message(achievements, self.user)
        
        assert "Multiple Achievements Unlocked" in message
        assert "<b>2 achievements</b>" in message
        assert "• 💬 <b>Chatterbox</b>" in message
        assert "• 🤝 <b>Helpful</b>" in message
        assert "complete collection" in message