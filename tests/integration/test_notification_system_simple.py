"""
Simple integration test for notification system.

This module tests the notification system directly without complex mocking.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from telegram import User, Message, Chat
from telegram.ext import ContextTypes

from modules.leveling_notification_service import LevelingNotificationService
from modules.leveling_models import Achievement, LevelUpResult


class TestNotificationSystemSimple:
    """Simple integration tests for notification system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = LevelingNotificationService({
            'enabled': True,
            'use_emojis': True,
            'use_mentions': True,
            'celebration_style': 'enthusiastic'
        })
        
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
    
    @pytest.mark.asyncio
    async def test_direct_level_up_notification(self):
        """Test level up notification directly."""
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
        assert "400" in message_text
        assert "🆙" in message_text  # Level 5 milestone emoji
    
    @pytest.mark.asyncio
    async def test_direct_achievement_notification(self):
        """Test achievement notification directly."""
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
    async def test_direct_multiple_achievements_notification(self):
        """Test multiple achievements notification directly."""
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