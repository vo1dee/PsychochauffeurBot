"""
Integration tests for leveling notification system.

This module tests the integration between the user leveling service
and the notification service for level-ups and achievement unlocks.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

from modules.user_leveling_service import UserLevelingService
from modules.leveling_notification_service import LevelingNotificationService
from modules.leveling_models import UserStats, Achievement, LevelUpResult


class TestLevelingNotificationsIntegration:
    """Integration tests for leveling notifications."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock configuration
        self.config = {
            'enabled': True,
            'notifications_enabled': True,
            'notifications': {
                'enabled': True,
                'use_emojis': True,
                'use_mentions': True,
                'celebration_style': 'enthusiastic'
            }
        }
        
        # Create service with mocked dependencies
        self.service = UserLevelingService()
        self.service._service_config = self.config
        self.service._initialized = True
        
        # Mock components
        self.service.xp_calculator = Mock()
        self.service.level_manager = Mock()
        self.service.achievement_engine = Mock()
        self.service.user_stats_repo = Mock()
        self.service.achievement_repo = Mock()
        
        # Initialize notification service
        self.service.notification_service = LevelingNotificationService(self.config['notifications'])
        
        # Mock user and message
        self.user = Mock(spec=User)
        self.user.id = 123456
        self.user.username = "testuser"
        self.user.first_name = "Test"
        self.user.last_name = "User"
        self.user.is_bot = False
        
        self.message = Mock(spec=Message)
        self.message.from_user = self.user
        self.message.chat = Mock(spec=Chat)
        self.message.chat.id = -100123456
        self.message.chat.type = 'supergroup'
        self.message.text = "Hello world!"
        self.message.reply_text = AsyncMock()
        
        self.context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    @pytest.mark.asyncio
    async def test_level_up_notification_integration(self):
        """Test level up notification through the full service integration."""
        # Mock user stats
        user_stats = UserStats(
            user_id=123456,
            chat_id=-100123456,
            xp=400,
            level=5,
            messages_count=100
        )
        
        # Mock level up result
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=4,
            new_level=5,
            total_xp=400
        )
        
        # Mock XP calculation
        self.service.xp_calculator.calculate_total_message_xp.return_value = (1, {})
        
        # Mock repository responses
        self.service.user_stats_repo.get_user_stats = AsyncMock(return_value=user_stats)
        self.service.user_stats_repo.update_user_stats = AsyncMock()
        
        # Mock level manager
        self.service.level_manager.calculate_level.side_effect = [4, 5]  # old level, new level
        
        # Mock achievement engine
        self.service.achievement_engine.check_achievements = AsyncMock(return_value=[])
        
        # Mock _ensure_user_exists
        with patch.object(self.service, '_ensure_user_exists', new_callable=AsyncMock):
            # Process message that should trigger level up
            await self.service._award_xp_to_user(
                123456, -100123456, 1, self.message, self.context
            )
        
        # Verify notification was sent
        self.message.reply_text.assert_called_once()
        
        # Check notification content
        call_args = self.message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "Congratulations" in message_text
        assert "Level 5" in message_text
        assert "🆙" in message_text  # Level 5 milestone emoji
        assert "/profile" in message_text
    
    @pytest.mark.asyncio
    async def test_achievement_notification_integration(self):
        """Test achievement notification through the full service integration."""
        # Mock user stats
        user_stats = UserStats(
            user_id=123456,
            chat_id=-100123456,
            xp=100,
            level=3,
            messages_count=100
        )
        
        # Mock achievement
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
        
        # Mock XP calculation
        self.service.xp_calculator.calculate_total_message_xp.return_value = (1, {})
        
        # Mock repository responses
        self.service.user_stats_repo.get_user_stats = AsyncMock(return_value=user_stats)
        self.service.user_stats_repo.update_user_stats = AsyncMock()
        
        # Mock level manager (no level up)
        self.service.level_manager.calculate_level.return_value = 3
        
        # Mock achievement engine
        self.service.achievement_engine.check_achievements = AsyncMock(return_value=[achievement])
        
        # Mock _ensure_user_exists
        with patch.object(self.service, '_ensure_user_exists', new_callable=AsyncMock):
            # Process message that should trigger achievement
            await self.service._award_xp_to_user(
                123456, -100123456, 1, self.message, self.context
            )
        
        # Verify notification was sent
        self.message.reply_text.assert_called_once()
        
        # Check notification content
        call_args = self.message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "Achievement Unlocked" in message_text
        assert "Chatterbox" in message_text
        assert "💬" in message_text
        assert "Send 100+ messages" in message_text
    
    @pytest.mark.asyncio
    async def test_multiple_achievements_notification_integration(self):
        """Test multiple achievements notification through the full service integration."""
        # Mock user stats
        user_stats = UserStats(
            user_id=123456,
            chat_id=-100123456,
            xp=100,
            level=3,
            messages_count=100,
            thanks_received=5
        )
        
        # Mock achievements
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
        
        # Mock XP calculation
        self.service.xp_calculator.calculate_total_message_xp.return_value = (1, {})
        
        # Mock repository responses
        self.service.user_stats_repo.get_user_stats = AsyncMock(return_value=user_stats)
        self.service.user_stats_repo.update_user_stats = AsyncMock()
        
        # Mock level manager (no level up)
        self.service.level_manager.calculate_level.return_value = 3
        
        # Mock achievement engine
        self.service.achievement_engine.check_achievements = AsyncMock(return_value=achievements)
        
        # Mock _ensure_user_exists
        with patch.object(self.service, '_ensure_user_exists', new_callable=AsyncMock):
            # Process message that should trigger multiple achievements
            await self.service._award_xp_to_user(
                123456, -100123456, 1, self.message, self.context
            )
        
        # Verify notification was sent
        self.message.reply_text.assert_called_once()
        
        # Check notification content
        call_args = self.message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "Multiple Achievements Unlocked" in message_text
        assert "2 achievements" in message_text
        assert "Chatterbox" in message_text
        assert "Helpful" in message_text
        assert "💬" in message_text
        assert "🤝" in message_text
    
    @pytest.mark.asyncio
    async def test_level_up_and_achievement_notification_integration(self):
        """Test both level up and achievement notifications in one event."""
        # Mock user stats
        user_stats = UserStats(
            user_id=123456,
            chat_id=-100123456,
            xp=399,  # Will become 400 after XP award
            level=4,  # Will become 5
            messages_count=100
        )
        
        # Mock level up result
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=4,
            new_level=5,
            total_xp=400
        )
        
        # Mock achievement
        achievement = Achievement(
            id="level_up",
            title="Level Up!",
            description="Reach level 5",
            emoji="🆙",
            sticker="🆙",
            condition_type="level",
            condition_value=5,
            category="progression"
        )
        
        # Mock XP calculation
        self.service.xp_calculator.calculate_total_message_xp.return_value = (1, {})
        
        # Mock repository responses
        self.service.user_stats_repo.get_user_stats = AsyncMock(return_value=user_stats)
        self.service.user_stats_repo.update_user_stats = AsyncMock()
        
        # Mock level manager
        self.service.level_manager.calculate_level.side_effect = [4, 5]  # old level, new level
        
        # Mock achievement engine
        self.service.achievement_engine.check_achievements = AsyncMock(return_value=[achievement])
        
        # Mock _ensure_user_exists
        with patch.object(self.service, '_ensure_user_exists', new_callable=AsyncMock):
            # Process message that should trigger both level up and achievement
            await self.service._award_xp_to_user(
                123456, -100123456, 1, self.message, self.context
            )
        
        # Verify both notifications were sent (2 calls to reply_text)
        assert self.message.reply_text.call_count == 2
        
        # Check both notification contents
        calls = self.message.reply_text.call_args_list
        
        # First call should be level up notification
        level_up_message = calls[0][0][0]
        assert "Congratulations" in level_up_message
        assert "Level 5" in level_up_message
        
        # Second call should be achievement notification
        achievement_message = calls[1][0][0]
        assert "Achievement Unlocked" in achievement_message
        assert "Level Up!" in achievement_message
        assert "🆙" in achievement_message
    
    @pytest.mark.asyncio
    async def test_notifications_disabled_integration(self):
        """Test that no notifications are sent when disabled."""
        # Disable notifications
        self.service._service_config['notifications_enabled'] = False
        
        # Mock user stats
        user_stats = UserStats(
            user_id=123456,
            chat_id=-100123456,
            xp=400,
            level=5,
            messages_count=100
        )
        
        # Mock level up result
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=4,
            new_level=5,
            total_xp=400
        )
        
        # Mock XP calculation
        self.service.xp_calculator.calculate_total_message_xp.return_value = (1, {})
        
        # Mock repository responses
        self.service.user_stats_repo.get_user_stats = AsyncMock(return_value=user_stats)
        self.service.user_stats_repo.update_user_stats = AsyncMock()
        
        # Mock level manager
        self.service.level_manager.calculate_level.side_effect = [4, 5]
        
        # Mock achievement engine
        self.service.achievement_engine.check_achievements = AsyncMock(return_value=[])
        
        # Mock _ensure_user_exists
        with patch.object(self.service, '_ensure_user_exists', new_callable=AsyncMock):
            # Process message
            await self.service._award_xp_to_user(
                123456, -100123456, 1, self.message, self.context
            )
        
        # Verify no notifications were sent
        self.message.reply_text.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_notification_error_handling_integration(self):
        """Test error handling in notification delivery during integration."""
        # Mock user stats
        user_stats = UserStats(
            user_id=123456,
            chat_id=-100123456,
            xp=400,
            level=5,
            messages_count=100
        )
        
        # Mock level up result
        level_up_result = LevelUpResult(
            user_id=123456,
            old_level=4,
            new_level=5,
            total_xp=400
        )
        
        # Mock reply_text to raise an exception
        self.message.reply_text.side_effect = Exception("Network error")
        
        # Mock XP calculation
        self.service.xp_calculator.calculate_total_message_xp.return_value = (1, {})
        
        # Mock repository responses
        self.service.user_stats_repo.get_user_stats = AsyncMock(return_value=user_stats)
        self.service.user_stats_repo.update_user_stats = AsyncMock()
        
        # Mock level manager
        self.service.level_manager.calculate_level.side_effect = [4, 5]
        
        # Mock achievement engine
        self.service.achievement_engine.check_achievements = AsyncMock(return_value=[])
        
        # Mock _ensure_user_exists
        with patch.object(self.service, '_ensure_user_exists', new_callable=AsyncMock):
            # Process message - should not raise exception despite notification error
            await self.service._award_xp_to_user(
                123456, -100123456, 1, self.message, self.context
            )
        
        # Verify notification was attempted but failed gracefully
        self.message.reply_text.assert_called_once()
        
        # Verify user stats were still updated despite notification failure
        self.service.user_stats_repo.update_user_stats.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_notification_configuration_integration(self):
        """Test different notification configurations."""
        # Test minimal style
        self.service.notification_service.update_config({
            'celebration_style': 'minimal',
            'use_emojis': False,
            'use_mentions': False
        })
        
        # Mock user stats
        user_stats = UserStats(
            user_id=123456,
            chat_id=-100123456,
            xp=400,
            level=5,
            messages_count=100
        )
        
        # Mock XP calculation
        self.service.xp_calculator.calculate_total_message_xp.return_value = (1, {})
        
        # Mock repository responses
        self.service.user_stats_repo.get_user_stats = AsyncMock(return_value=user_stats)
        self.service.user_stats_repo.update_user_stats = AsyncMock()
        
        # Mock level manager
        self.service.level_manager.calculate_level.side_effect = [4, 5]
        
        # Mock achievement engine
        self.service.achievement_engine.check_achievements = AsyncMock(return_value=[])
        
        # Mock _ensure_user_exists
        with patch.object(self.service, '_ensure_user_exists', new_callable=AsyncMock):
            # Process message
            await self.service._award_xp_to_user(
                123456, -100123456, 1, self.message, self.context
            )
        
        # Verify notification was sent
        self.message.reply_text.assert_called_once()
        
        # Check notification content (should be minimal style)
        call_args = self.message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "reached Level 5" in message_text
        # Should not have HTML formatting or excessive emojis
        assert "<b>" not in message_text
        assert "🎉" not in message_text