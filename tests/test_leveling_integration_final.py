"""
Final Integration Tests for User Leveling System

This test suite validates the complete end-to-end functionality of the leveling system
including message processing, XP calculation, level progression, achievement unlocking,
and notification system.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List

from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

from modules.user_leveling_service import UserLevelingService
from modules.leveling_models import UserStats, Achievement, UserProfile
from modules.xp_calculator import XPCalculator
from modules.level_manager import LevelManager
from modules.achievement_engine import AchievementEngine
from modules.repositories import UserStatsRepository, AchievementRepository
from modules.leveling_notification_service import LevelingNotificationService
from modules.service_registry import ServiceRegistry


class TestLevelingSystemIntegration:
    """Test complete leveling system integration."""
    
    @pytest.fixture
    def mock_service_registry(self):
        """Create a mock service registry with required services."""
        registry = Mock(spec=ServiceRegistry)
        
        # Mock config manager
        config_manager = Mock()
        config_manager.get_config = AsyncMock(return_value={
            'enabled': True,
            'overrides': {
                'enabled': True,
                'xp_rates': {'message': 1, 'link': 3, 'thanks': 5},
                'level_formula': {'base_xp': 50, 'multiplier': 2.0},
                'notifications': {'enabled': True, 'level_up_enabled': True, 'achievements_enabled': True}
            }
        })
        
        # Mock database
        database = Mock()
        database.execute_query = AsyncMock()
        database.fetch_one = AsyncMock()
        database.fetch_all = AsyncMock()
        
        registry.get_service.side_effect = lambda name: {
            'config_manager': config_manager,
            'database': database
        }.get(name)
        
        return registry
    
    @pytest.fixture
    def leveling_service(self, mock_service_registry):
        """Create a leveling service with mocked dependencies."""
        config_manager = mock_service_registry.get_service('config_manager')
        database = mock_service_registry.get_service('database')
        
        service = UserLevelingService(config_manager=config_manager, database=database)
        
        # Mock the repositories to avoid database calls
        service.user_stats_repo = Mock(spec=UserStatsRepository)
        service.achievement_repo = Mock(spec=AchievementRepository)
        service.notification_service = Mock(spec=LevelingNotificationService)
        
        return service
    
    @pytest.fixture
    def mock_update_and_context(self):
        """Create mock Telegram update and context."""
        # Create mock user
        user = Mock(spec=User)
        user.id = 12345
        user.username = "testuser"
        user.is_bot = False
        
        # Create mock chat
        chat = Mock(spec=Chat)
        chat.id = -67890
        chat.type = "group"
        
        # Create mock message
        message = Mock(spec=Message)
        message.from_user = user
        message.chat = chat
        message.text = "Hello world!"
        message.message_id = 1
        message.date = datetime.now()
        
        # Create mock update
        update = Mock(spec=Update)
        update.message = message
        update.effective_chat = chat
        update.effective_user = user
        
        # Create mock context
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot_data = {'service_registry': Mock()}
        
        return update, context
    
    @pytest.mark.asyncio
    async def test_basic_message_processing(self, leveling_service, mock_update_and_context):
        """Test basic message processing awards XP correctly."""
        update, context = mock_update_and_context
        
        # Mock user stats
        user_stats = UserStats(
            user_id=12345,
            chat_id=-67890,
            xp=0,
            level=1,
            messages_count=0
        )
        
        leveling_service.user_stats_repo.get_user_stats.return_value = user_stats
        leveling_service.user_stats_repo.update_user_stats.return_value = None
        leveling_service.achievement_repo.get_user_achievements.return_value = []
        
        # Process message
        await leveling_service.process_message(update, context)
        
        # Verify XP was awarded
        assert user_stats.xp == 1  # 1 XP for message
        assert user_stats.messages_count == 1
        
        # Verify database update was called
        leveling_service.user_stats_repo.update_user_stats.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_link_sharing_awards_bonus_xp(self, leveling_service, mock_update_and_context):
        """Test that sharing links awards bonus XP."""
        update, context = mock_update_and_context
        update.message.text = "Check this out: https://example.com"
        
        # Mock user stats
        user_stats = UserStats(
            user_id=12345,
            chat_id=-67890,
            xp=0,
            level=1,
            messages_count=0,
            links_shared=0
        )
        
        leveling_service.user_stats_repo.get_user_stats.return_value = user_stats
        leveling_service.user_stats_repo.update_user_stats.return_value = None
        leveling_service.achievement_repo.get_user_achievements.return_value = []
        
        # Process message
        await leveling_service.process_message(update, context)
        
        # Verify XP was awarded (1 for message + 3 for link)
        assert user_stats.xp == 4
        assert user_stats.messages_count == 1
        assert user_stats.links_shared == 1
    
    @pytest.mark.asyncio
    async def test_thanks_detection_awards_xp_to_mentioned_user(self, leveling_service, mock_update_and_context):
        """Test that thanking a user awards XP to the mentioned user."""
        update, context = mock_update_and_context
        update.message.text = "Thanks @testuser2 for the help!"
        
        # Mock the thanked user stats
        thanked_user_stats = UserStats(
            user_id=54321,
            chat_id=-67890,
            xp=0,
            level=1,
            thanks_received=0
        )
        
        # Mock sender stats
        sender_stats = UserStats(
            user_id=12345,
            chat_id=-67890,
            xp=0,
            level=1,
            messages_count=0
        )
        
        def mock_get_user_stats(user_id, chat_id):
            if user_id == 12345:
                return sender_stats
            elif user_id == 54321:
                return thanked_user_stats
            return None
        
        leveling_service.user_stats_repo.get_user_stats.side_effect = mock_get_user_stats
        leveling_service.user_stats_repo.update_user_stats.return_value = None
        leveling_service.achievement_repo.get_user_achievements.return_value = []
        
        # Mock XP calculator to detect thanks
        with patch.object(leveling_service.xp_calculator, 'calculate_total_message_xp') as mock_calc:
            mock_calc.return_value = (1, {54321: 5})  # 1 XP for sender, 5 XP for thanked user
            
            # Process message
            await leveling_service.process_message(update, context)
        
        # Verify sender got message XP
        assert sender_stats.xp == 1
        assert sender_stats.messages_count == 1
        
        # Verify thanked user got thanks XP
        assert thanked_user_stats.xp == 5
        assert thanked_user_stats.thanks_received == 1
    
    @pytest.mark.asyncio
    async def test_level_up_triggers_notification(self, leveling_service, mock_update_and_context):
        """Test that leveling up triggers a notification."""
        update, context = mock_update_and_context
        
        # Mock user stats close to level up (49 XP, needs 50 for level 2)
        user_stats = UserStats(
            user_id=12345,
            chat_id=-67890,
            xp=49,
            level=1,
            messages_count=99
        )
        
        leveling_service.user_stats_repo.get_user_stats.return_value = user_stats
        leveling_service.user_stats_repo.update_user_stats.return_value = None
        leveling_service.achievement_repo.get_user_achievements.return_value = []
        leveling_service.notification_service.send_level_up_notification = AsyncMock()
        
        # Process message (should trigger level up)
        await leveling_service.process_message(update, context)
        
        # Verify level up occurred
        assert user_stats.level == 2
        assert user_stats.xp == 50
        
        # Verify notification was sent
        leveling_service.notification_service.send_level_up_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_achievement_unlocking(self, leveling_service, mock_update_and_context):
        """Test that achievements are unlocked when conditions are met."""
        update, context = mock_update_and_context
        
        # Mock user stats that will trigger achievement (99 messages, next one triggers "100 messages" achievement)
        user_stats = UserStats(
            user_id=12345,
            chat_id=-67890,
            xp=50,
            level=2,
            messages_count=99
        )
        
        # Mock achievement
        achievement = Achievement(
            id="chatterbox",
            title="Chatterbox",
            description="Send 100 messages",
            emoji="💬",
            sticker="💬",
            condition_type="messages_count",
            condition_value=100,
            category="activity"
        )
        
        leveling_service.user_stats_repo.get_user_stats.return_value = user_stats
        leveling_service.user_stats_repo.update_user_stats.return_value = None
        leveling_service.achievement_repo.get_user_achievements.return_value = []
        leveling_service.achievement_engine.check_achievements.return_value = [achievement]
        leveling_service.achievement_engine.unlock_achievement = AsyncMock()
        leveling_service.notification_service.send_achievement_notification = AsyncMock()
        
        # Process message (should trigger achievement)
        await leveling_service.process_message(update, context)
        
        # Verify achievement was unlocked
        leveling_service.achievement_engine.unlock_achievement.assert_called_once()
        leveling_service.notification_service.send_achievement_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rate_limiting_prevents_xp_farming(self, leveling_service, mock_update_and_context):
        """Test that rate limiting prevents XP farming."""
        update, context = mock_update_and_context
        
        # Enable rate limiting in config
        leveling_service._current_leveling_config.rate_limiting.enabled = True
        leveling_service._current_leveling_config.rate_limiting.max_xp_per_minute = 5
        
        user_stats = UserStats(
            user_id=12345,
            chat_id=-67890,
            xp=0,
            level=1,
            messages_count=0
        )
        
        leveling_service.user_stats_repo.get_user_stats.return_value = user_stats
        leveling_service.user_stats_repo.update_user_stats.return_value = None
        leveling_service.achievement_repo.get_user_achievements.return_value = []
        
        # Process multiple messages rapidly
        for i in range(10):
            await leveling_service.process_message(update, context)
        
        # Should be rate limited after 5 XP
        assert user_stats.xp <= 5
        assert leveling_service._stats['rate_limited'] > 0
    
    @pytest.mark.asyncio
    async def test_error_handling_doesnt_crash_service(self, leveling_service, mock_update_and_context):
        """Test that errors in processing don't crash the service."""
        update, context = mock_update_and_context
        
        # Mock database error
        leveling_service.user_stats_repo.get_user_stats.side_effect = Exception("Database error")
        
        # Process message should not raise exception
        try:
            await leveling_service.process_message(update, context)
        except Exception:
            pytest.fail("Service should handle errors gracefully")
        
        # Error should be recorded in stats
        assert leveling_service._stats['errors'] > 0
    
    @pytest.mark.asyncio
    async def test_profile_command_integration(self, leveling_service):
        """Test profile command returns correct user data."""
        user_id = 12345
        chat_id = -67890
        
        # Mock user stats
        user_stats = UserStats(
            user_id=user_id,
            chat_id=chat_id,
            xp=150,
            level=3,
            messages_count=75,
            links_shared=10,
            thanks_received=5
        )
        
        # Mock achievements
        achievements = [
            Achievement(
                id="first_message",
                title="First Steps",
                description="Send your first message",
                emoji="👶",
                sticker="👶",
                condition_type="messages_count",
                condition_value=1,
                category="activity"
            )
        ]
        
        leveling_service.user_stats_repo.get_user_stats.return_value = user_stats
        leveling_service.achievement_repo.get_user_achievements.return_value = achievements
        
        # Get user profile
        profile = await leveling_service.get_user_profile(user_id, chat_id)
        
        # Verify profile data
        assert isinstance(profile, UserProfile)
        assert profile.user_id == user_id
        assert profile.level == 3
        assert profile.xp == 150
        assert profile.next_level_xp == 400  # Level 4 threshold
        assert len(profile.achievements) == 1
        assert profile.stats['messages_count'] == 75
    
    @pytest.mark.asyncio
    async def test_leaderboard_functionality(self, leveling_service):
        """Test leaderboard returns correctly ranked users."""
        chat_id = -67890
        
        # Mock leaderboard data
        leaderboard_stats = [
            UserStats(user_id=1, chat_id=chat_id, xp=500, level=5, messages_count=200),
            UserStats(user_id=2, chat_id=chat_id, xp=300, level=4, messages_count=150),
            UserStats(user_id=3, chat_id=chat_id, xp=100, level=2, messages_count=50),
        ]
        
        leveling_service.user_stats_repo.get_leaderboard.return_value = leaderboard_stats
        leveling_service.achievement_repo.get_user_achievements.return_value = []
        
        # Get leaderboard
        leaderboard = await leveling_service.get_leaderboard(chat_id, limit=10)
        
        # Verify leaderboard is correctly ordered
        assert len(leaderboard) == 3
        assert leaderboard[0].user_id == 1  # Highest XP first
        assert leaderboard[0].rank == 1
        assert leaderboard[1].user_id == 2
        assert leaderboard[1].rank == 2
        assert leaderboard[2].user_id == 3
        assert leaderboard[2].rank == 3


class TestMessageHandlerIntegration:
    """Test integration with message handler pipeline."""
    
    @pytest.mark.asyncio
    async def test_message_handler_calls_leveling_service(self):
        """Test that message handler properly calls leveling service."""
        from modules.message_handler import _process_leveling_system
        
        # Mock update and context
        update = Mock(spec=Update)
        update.message = Mock()
        update.message.from_user = Mock()
        update.message.from_user.is_bot = False
        update.effective_chat = Mock()
        update.effective_chat.type = "group"
        
        # Mock service registry and leveling service
        leveling_service = Mock()
        leveling_service.is_enabled.return_value = True
        leveling_service.process_message = AsyncMock()
        
        service_registry = Mock()
        service_registry.get_service.return_value = leveling_service
        
        context = Mock()
        context.bot_data = {'service_registry': service_registry}
        
        # Call the integration function
        await _process_leveling_system(update, context)
        
        # Verify leveling service was called
        leveling_service.process_message.assert_called_once_with(update, context)
    
    @pytest.mark.asyncio
    async def test_message_handler_handles_missing_service_gracefully(self):
        """Test that message handler handles missing leveling service gracefully."""
        from modules.message_handler import _process_leveling_system
        
        # Mock update and context with no service registry
        update = Mock(spec=Update)
        context = Mock()
        context.bot_data = {}
        
        # Should not raise exception
        try:
            await _process_leveling_system(update, context)
        except Exception:
            pytest.fail("Should handle missing service gracefully")
    
    @pytest.mark.asyncio
    async def test_new_message_handler_does_not_call_leveling(self):
        """Test that the new message handler does NOT call leveling to avoid duplication."""
        from modules.handlers.message_handlers import handle_message
        
        # Mock update and context
        update = Mock(spec=Update)
        update.message = Mock()
        update.message.text = "Hello world!"
        update.message.from_user = Mock()
        update.message.from_user.id = 12345
        update.message.from_user.username = "testuser"
        update.message.from_user.is_bot = False
        update.effective_chat = Mock()
        update.effective_chat.id = -67890
        update.effective_chat.type = "group"
        
        # Mock service registry and leveling service
        leveling_service = Mock()
        leveling_service.is_enabled.return_value = True
        leveling_service.process_message = AsyncMock()
        
        service_registry = Mock()
        service_registry.get_service.return_value = leveling_service
        
        context = Mock()
        context.bot_data = {'service_registry': service_registry}
        context.application = Mock()
        context.application.bot_data = {'service_registry': service_registry}
        
        # Mock all the dependencies that handle_message needs
        with patch('modules.handlers.message_handlers.update_message_history'), \
             patch('modules.handlers.message_handlers.should_restrict_user', return_value=False), \
             patch('modules.handlers.message_handlers.process_message_content', return_value=("Hello world!", [])), \
             patch('modules.handlers.message_handlers.needs_gpt_response', return_value=(False, None)), \
             patch('modules.handlers.message_handlers.handle_random_gpt_response'):
            
            # Call the new message handler
            await handle_message(update, context)
        
        # Verify leveling service was NOT called (to avoid duplication)
        leveling_service.process_message.assert_not_called()


class TestServiceRegistryIntegration:
    """Test service registry integration."""
    
    @pytest.mark.asyncio
    async def test_leveling_service_registration(self):
        """Test that leveling service can be properly registered and retrieved."""
        from modules.service_registry import ServiceRegistry
        from modules.service_factories import ServiceFactory
        
        # Create service registry
        registry = ServiceRegistry()
        
        # Mock dependencies
        config_manager = Mock()
        database = Mock()
        
        registry.register_instance('config_manager', config_manager)
        registry.register_instance('database', database)
        
        # Register leveling service
        registry.register_factory(
            'user_leveling_service',
            type(None),
            ServiceFactory.create_user_leveling_service,
            dependencies=['config_manager', 'database']
        )
        
        # Verify service can be retrieved
        service = registry.get_service('user_leveling_service')
        assert service is not None
        assert isinstance(service, UserLevelingService)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])