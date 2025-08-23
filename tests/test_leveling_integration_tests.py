"""
Integration tests for the User Leveling System message processing pipeline.

This module tests the complete integration of all leveling system components
working together in realistic scenarios, including message processing,
XP calculation, level progression, achievement unlocking, and notifications.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

from telegram import Update, Message, User, Chat, Bot
from telegram.ext import ContextTypes

# Import leveling system components
from modules.user_leveling_service import UserLevelingService
from modules.xp_calculator import XPCalculator
from modules.level_manager import LevelManager
from modules.achievement_engine import AchievementEngine
from modules.leveling_models import UserStats, Achievement, UserAchievement, LevelUpResult
from modules.repositories import UserStatsRepository, AchievementRepository

# Import test base classes
from tests.base_test_classes import AsyncBaseTestCase, IntegrationTestCase


class TestLevelingSystemIntegration(AsyncBaseTestCase, IntegrationTestCase):
    """Integration tests for the complete leveling system."""
    
    async def setUp(self):
        """Set up integration test environment."""
        await super().setUp()
        
        # Create mock dependencies
        self.mock_config_manager = Mock()
        self.mock_config_manager.get.return_value = {
            'enabled': True,
            'level_base_xp': 50,
            'level_multiplier': 2.0,
            'notifications_enabled': True,
            'xp_rates': {
                'message': 1,
                'link': 3,
                'thanks': 5
            }
        }
        
        self.mock_database = AsyncMock()
        
        # Create leveling service
        self.leveling_service = UserLevelingService(
            config_manager=self.mock_config_manager,
            database=self.mock_database
        )
        
        # Mock repositories
        self.mock_user_stats_repo = AsyncMock(spec=UserStatsRepository)
        self.mock_achievement_repo = AsyncMock(spec=AchievementRepository)
        
        # Mock notification service
        self.mock_notification_service = AsyncMock()
        
        # Initialize service with mocked dependencies
        with patch('modules.user_leveling_service.UserStatsRepository', return_value=self.mock_user_stats_repo), \
             patch('modules.user_leveling_service.AchievementRepository', return_value=self.mock_achievement_repo), \
             patch('modules.user_leveling_service.LevelingNotificationService', return_value=self.mock_notification_service):
            await self.leveling_service.initialize()
    
    async def tearDown(self):
        """Clean up integration test environment."""
        if hasattr(self, 'leveling_service'):
            await self.leveling_service.shutdown()
        await super().tearDown()
    
    def create_telegram_message(self, text: str, user_id: int = 12345, chat_id: int = -1001234567890,
                               username: str = "testuser", reply_to_message=None, **kwargs) -> Message:
        """Create a realistic Telegram message object."""
        # Create user
        user = User(
            id=user_id,
            is_bot=False,
            first_name="Test",
            last_name="User",
            username=username,
            language_code="en"
        )
        
        # Create chat
        chat = Chat(
            id=chat_id,
            type=Chat.SUPERGROUP,
            title="Test Group",
            description="A test group chat"
        )
        
        # Create message
        message = Message(
            message_id=1,
            date=datetime.now(),
            chat=chat,
            from_user=user,
            text=text,
            reply_to_message=reply_to_message
        )
        
        # Apply additional attributes
        for key, value in kwargs.items():
            setattr(message, key, value)
        
        return message
    
    def create_telegram_update(self, message: Message) -> Update:
        """Create a Telegram update with the given message."""
        return Update(
            update_id=1,
            message=message
        )
    
    def create_mock_context(self) -> Mock:
        """Create a mock Telegram context."""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock(spec=Bot)
        context.bot.send_message = AsyncMock()
        context.bot.send_sticker = AsyncMock()
        return context


class TestBasicMessageProcessing(TestLevelingSystemIntegration):
    """Test basic message processing integration."""
    
    @pytest.mark.asyncio
    async def test_process_simple_message(self):
        """Test processing a simple text message."""
        # Create test message
        message = self.create_telegram_message("Hello world!")
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Mock user stats (new user)
        self.mock_user_stats_repo.get_user_stats.return_value = None
        self.mock_user_stats_repo.create_user_stats.return_value = UserStats(
            user_id=12345,
            chat_id=-1001234567890,
            xp=0,
            level=1,
            messages_count=0,
            links_shared=0,
            thanks_received=0
        )
        
        # Mock no achievements unlocked
        self.mock_achievement_repo.get_user_achievements.return_value = []
        
        # Process message
        await self.leveling_service.process_message(update, context)
        
        # Verify user stats were created and updated
        self.mock_user_stats_repo.create_user_stats.assert_called_once_with(12345, -1001234567890)
        self.mock_user_stats_repo.update_user_stats.assert_called_once()
        
        # Verify XP was awarded (1 XP for message)
        updated_stats = self.mock_user_stats_repo.update_user_stats.call_args[0][0]
        self.assertEqual(updated_stats.xp, 1)
        self.assertEqual(updated_stats.messages_count, 1)
    
    @pytest.mark.asyncio
    async def test_process_message_with_link(self):
        """Test processing a message with a link."""
        # Create test message with link
        message = self.create_telegram_message("Check out https://example.com")
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Mock existing user stats
        existing_stats = UserStats(
            user_id=12345,
            chat_id=-1001234567890,
            xp=10,
            level=1,
            messages_count=5,
            links_shared=0,
            thanks_received=0
        )
        self.mock_user_stats_repo.get_user_stats.return_value = existing_stats
        
        # Process message
        await self.leveling_service.process_message(update, context)
        
        # Verify XP was awarded (1 XP for message + 3 XP for link = 4 XP total)
        updated_stats = self.mock_user_stats_repo.update_user_stats.call_args[0][0]
        self.assertEqual(updated_stats.xp, 14)  # 10 + 4
        self.assertEqual(updated_stats.messages_count, 6)  # 5 + 1
        self.assertEqual(updated_stats.links_shared, 1)  # 0 + 1
    
    @pytest.mark.asyncio
    async def test_process_thank_you_message(self):
        """Test processing a thank you message."""
        # Create reply-to message
        replied_user = User(id=54321, is_bot=False, first_name="Replied", username="replieduser")
        replied_chat = Chat(id=-1001234567890, type=Chat.SUPERGROUP, title="Test Group")
        reply_to_message = Message(
            message_id=2,
            date=datetime.now(),
            chat=replied_chat,
            from_user=replied_user,
            text="Original message"
        )
        
        # Create thank you message
        message = self.create_telegram_message("Thank you!", reply_to_message=reply_to_message)
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Mock user stats for both users
        sender_stats = UserStats(user_id=12345, chat_id=-1001234567890, xp=5, level=1)
        thanked_stats = UserStats(user_id=54321, chat_id=-1001234567890, xp=10, level=1)
        
        def mock_get_user_stats(user_id, chat_id):
            if user_id == 12345:
                return sender_stats
            elif user_id == 54321:
                return thanked_stats
            return None
        
        self.mock_user_stats_repo.get_user_stats.side_effect = mock_get_user_stats
        
        # Process message
        await self.leveling_service.process_message(update, context)
        
        # Verify both users' stats were updated
        self.assertEqual(self.mock_user_stats_repo.update_user_stats.call_count, 2)
        
        # Check sender got message XP (1 XP)
        sender_update_call = None
        thanked_update_call = None
        
        for call in self.mock_user_stats_repo.update_user_stats.call_args_list:
            stats = call[0][0]
            if stats.user_id == 12345:
                sender_update_call = stats
            elif stats.user_id == 54321:
                thanked_update_call = stats
        
        self.assertIsNotNone(sender_update_call)
        self.assertIsNotNone(thanked_update_call)
        
        # Sender should get 1 XP for message
        self.assertEqual(sender_update_call.xp, 6)  # 5 + 1
        
        # Thanked user should get 5 XP for being thanked
        self.assertEqual(thanked_update_call.xp, 15)  # 10 + 5
        self.assertEqual(thanked_update_call.thanks_received, 1)
    
    @pytest.mark.asyncio
    async def test_ignore_bot_messages(self):
        """Test that bot messages are ignored."""
        # Create bot message
        bot_user = User(id=98765, is_bot=True, first_name="Bot", username="testbot")
        chat = Chat(id=-1001234567890, type=Chat.SUPERGROUP, title="Test Group")
        
        message = Message(
            message_id=1,
            date=datetime.now(),
            chat=chat,
            from_user=bot_user,
            text="Bot message"
        )
        
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Process message
        await self.leveling_service.process_message(update, context)
        
        # Verify no database operations were performed
        self.mock_user_stats_repo.get_user_stats.assert_not_called()
        self.mock_user_stats_repo.update_user_stats.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_ignore_private_messages(self):
        """Test that private messages are ignored."""
        # Create private message
        user = User(id=12345, is_bot=False, first_name="Test", username="testuser")
        private_chat = Chat(id=12345, type=Chat.PRIVATE, username="testuser")
        
        message = Message(
            message_id=1,
            date=datetime.now(),
            chat=private_chat,
            from_user=user,
            text="Private message"
        )
        
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Process message
        await self.leveling_service.process_message(update, context)
        
        # Verify no database operations were performed
        self.mock_user_stats_repo.get_user_stats.assert_not_called()
        self.mock_user_stats_repo.update_user_stats.assert_not_called()


class TestLevelUpIntegration(TestLevelingSystemIntegration):
    """Test level up integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_level_up_notification(self):
        """Test that level up triggers notification."""
        # Create message that will cause level up
        message = self.create_telegram_message("Hello world!")
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Mock user stats just before level up (49 XP, level 1)
        existing_stats = UserStats(
            user_id=12345,
            chat_id=-1001234567890,
            xp=49,
            level=1,
            messages_count=49,
            links_shared=0,
            thanks_received=0
        )
        self.mock_user_stats_repo.get_user_stats.return_value = existing_stats
        
        # Process message (should add 1 XP, reaching 50 XP and level 2)
        await self.leveling_service.process_message(update, context)
        
        # Verify level up notification was sent
        self.mock_notification_service.send_level_up_notification.assert_called_once()
        
        # Verify user reached level 2
        updated_stats = self.mock_user_stats_repo.update_user_stats.call_args[0][0]
        self.assertEqual(updated_stats.level, 2)
        self.assertEqual(updated_stats.xp, 50)
    
    @pytest.mark.asyncio
    async def test_multiple_level_up(self):
        """Test multiple level ups in one message."""
        # Create message with link that will cause multiple level ups
        message = self.create_telegram_message("Check https://example.com")
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Mock user stats that will jump multiple levels (96 XP, level 2)
        # Adding 4 XP (1 + 3) will reach 100 XP = level 3
        existing_stats = UserStats(
            user_id=12345,
            chat_id=-1001234567890,
            xp=96,
            level=2,
            messages_count=50,
            links_shared=0,
            thanks_received=0
        )
        self.mock_user_stats_repo.get_user_stats.return_value = existing_stats
        
        # Process message
        await self.leveling_service.process_message(update, context)
        
        # Verify level up notification was sent
        self.mock_notification_service.send_level_up_notification.assert_called_once()
        
        # Verify user reached level 3
        updated_stats = self.mock_user_stats_repo.update_user_stats.call_args[0][0]
        self.assertEqual(updated_stats.level, 3)
        self.assertEqual(updated_stats.xp, 100)


class TestAchievementIntegration(TestLevelingSystemIntegration):
    """Test achievement system integration."""
    
    @pytest.mark.asyncio
    async def test_first_message_achievement(self):
        """Test unlocking first message achievement."""
        # Create first message
        message = self.create_telegram_message("Hello world!")
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Mock new user (no existing stats)
        self.mock_user_stats_repo.get_user_stats.return_value = None
        new_stats = UserStats(
            user_id=12345,
            chat_id=-1001234567890,
            xp=0,
            level=1,
            messages_count=0,
            links_shared=0,
            thanks_received=0
        )
        self.mock_user_stats_repo.create_user_stats.return_value = new_stats
        
        # Mock achievement engine to return first message achievement
        first_message_achievement = Achievement(
            id="novice",
            title="👶 Новачок",
            description="Send your first message",
            emoji="👶",
            sticker="👶",
            condition_type="messages_count",
            condition_value=1,
            category="activity"
        )
        
        # Mock achievement checking
        with patch.object(self.leveling_service.achievement_engine, 'check_achievements') as mock_check:
            mock_check.return_value = [first_message_achievement]
            
            # Process message
            await self.leveling_service.process_message(update, context)
        
        # Verify achievement notification was sent
        self.mock_notification_service.send_achievement_notification.assert_called_once()
        
        # Verify achievement was unlocked
        achievement_call = self.mock_notification_service.send_achievement_notification.call_args[0]
        self.assertEqual(achievement_call[2].id, "novice")  # achievement parameter
    
    @pytest.mark.asyncio
    async def test_multiple_achievements_unlock(self):
        """Test unlocking multiple achievements simultaneously."""
        # Create message that triggers multiple achievements
        message = self.create_telegram_message("Thanks! Check https://example.com")
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Mock user stats that will trigger multiple achievements
        existing_stats = UserStats(
            user_id=12345,
            chat_id=-1001234567890,
            xp=95,
            level=2,
            messages_count=99,  # Will reach 100 messages
            links_shared=9,     # Will reach 10 links
            thanks_received=0
        )
        self.mock_user_stats_repo.get_user_stats.return_value = existing_stats
        
        # Mock multiple achievements
        achievements = [
            Achievement(
                id="young_chatter",
                title="🐣 Молодий базіка",
                description="Send 100+ messages",
                emoji="🐣",
                sticker="🐣",
                condition_type="messages_count",
                condition_value=100,
                category="activity"
            ),
            Achievement(
                id="photo_lover",
                title="📸 Фотолюбитель",
                description="Share 10+ photos",
                emoji="📸",
                sticker="📸",
                condition_type="links_shared",
                condition_value=10,
                category="media"
            )
        ]
        
        # Mock achievement checking
        with patch.object(self.leveling_service.achievement_engine, 'check_achievements') as mock_check:
            mock_check.return_value = achievements
            
            # Process message
            await self.leveling_service.process_message(update, context)
        
        # Verify multiple achievement notifications were sent
        self.assertEqual(self.mock_notification_service.send_achievement_notification.call_count, 2)


class TestErrorHandlingIntegration(TestLevelingSystemIntegration):
    """Test error handling in integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test handling of database errors during message processing."""
        # Create test message
        message = self.create_telegram_message("Hello world!")
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Mock database error
        self.mock_user_stats_repo.get_user_stats.side_effect = Exception("Database connection failed")
        
        # Process message - should not crash
        try:
            await self.leveling_service.process_message(update, context)
        except Exception as e:
            self.fail(f"Message processing crashed with database error: {e}")
        
        # Service should remain operational
        self.assertTrue(self.leveling_service.is_enabled())
    
    @pytest.mark.asyncio
    async def test_achievement_engine_error_handling(self):
        """Test handling of achievement engine errors."""
        # Create test message
        message = self.create_telegram_message("Hello world!")
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Mock user stats
        existing_stats = UserStats(user_id=12345, chat_id=-1001234567890, xp=10, level=1)
        self.mock_user_stats_repo.get_user_stats.return_value = existing_stats
        
        # Mock achievement engine error
        with patch.object(self.leveling_service.achievement_engine, 'check_achievements') as mock_check:
            mock_check.side_effect = Exception("Achievement engine failed")
            
            # Process message - should not crash
            try:
                await self.leveling_service.process_message(update, context)
            except Exception as e:
                self.fail(f"Message processing crashed with achievement error: {e}")
        
        # User stats should still be updated
        self.mock_user_stats_repo.update_user_stats.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_notification_error_handling(self):
        """Test handling of notification errors."""
        # Create message that will cause level up
        message = self.create_telegram_message("Hello world!")
        update = self.create_telegram_update(message)
        context = self.create_mock_context()
        
        # Mock user stats just before level up
        existing_stats = UserStats(user_id=12345, chat_id=-1001234567890, xp=49, level=1)
        self.mock_user_stats_repo.get_user_stats.return_value = existing_stats
        
        # Mock notification error
        self.mock_notification_service.send_level_up_notification.side_effect = Exception("Notification failed")
        
        # Process message - should not crash
        try:
            await self.leveling_service.process_message(update, context)
        except Exception as e:
            self.fail(f"Message processing crashed with notification error: {e}")
        
        # User stats should still be updated
        updated_stats = self.mock_user_stats_repo.update_user_stats.call_args[0][0]
        self.assertEqual(updated_stats.level, 2)


class TestConcurrentProcessing(TestLevelingSystemIntegration):
    """Test concurrent message processing scenarios."""
    
    @pytest.mark.asyncio
    async def test_concurrent_messages_same_user(self):
        """Test processing concurrent messages from the same user."""
        # Create multiple messages from same user
        messages = [
            self.create_telegram_message(f"Message {i}", user_id=12345)
            for i in range(5)
        ]
        updates = [self.create_telegram_update(msg) for msg in messages]
        context = self.create_mock_context()
        
        # Mock user stats
        existing_stats = UserStats(user_id=12345, chat_id=-1001234567890, xp=0, level=1)
        self.mock_user_stats_repo.get_user_stats.return_value = existing_stats
        
        # Process messages concurrently
        tasks = [
            self.leveling_service.process_message(update, context)
            for update in updates
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all messages were processed
        self.assertEqual(self.mock_user_stats_repo.update_user_stats.call_count, 5)
    
    @pytest.mark.asyncio
    async def test_concurrent_messages_different_users(self):
        """Test processing concurrent messages from different users."""
        # Create messages from different users
        messages = [
            self.create_telegram_message(f"Message from user {i}", user_id=12345 + i)
            for i in range(5)
        ]
        updates = [self.create_telegram_update(msg) for msg in messages]
        context = self.create_mock_context()
        
        # Mock user stats for different users
        def mock_get_user_stats(user_id, chat_id):
            return UserStats(user_id=user_id, chat_id=chat_id, xp=0, level=1)
        
        self.mock_user_stats_repo.get_user_stats.side_effect = mock_get_user_stats
        
        # Process messages concurrently
        tasks = [
            self.leveling_service.process_message(update, context)
            for update in updates
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify no exceptions occurred
        for result in results:
            if isinstance(result, Exception):
                self.fail(f"Concurrent processing failed: {result}")
        
        # Verify all messages were processed
        self.assertEqual(self.mock_user_stats_repo.update_user_stats.call_count, 5)


class TestComplexScenarios(TestLevelingSystemIntegration):
    """Test complex real-world scenarios."""
    
    @pytest.mark.asyncio
    async def test_user_journey_simulation(self):
        """Test a complete user journey from first message to achievements."""
        context = self.create_mock_context()
        
        # Simulate user journey
        user_id = 12345
        chat_id = -1001234567890
        
        # Start with new user
        current_stats = None
        
        # Helper function to process message and update stats
        async def process_and_update(text, reply_to=None):
            nonlocal current_stats
            
            message = self.create_telegram_message(text, user_id=user_id, reply_to_message=reply_to)
            update = self.create_telegram_update(message)
            
            # Mock current stats
            if current_stats is None:
                self.mock_user_stats_repo.get_user_stats.return_value = None
                current_stats = UserStats(
                    user_id=user_id,
                    chat_id=chat_id,
                    xp=0,
                    level=1,
                    messages_count=0,
                    links_shared=0,
                    thanks_received=0
                )
                self.mock_user_stats_repo.create_user_stats.return_value = current_stats
            else:
                self.mock_user_stats_repo.get_user_stats.return_value = current_stats
            
            # Process message
            await self.leveling_service.process_message(update, context)
            
            # Update current stats based on what would happen
            if self.mock_user_stats_repo.update_user_stats.called:
                updated_stats = self.mock_user_stats_repo.update_user_stats.call_args[0][0]
                current_stats.xp = updated_stats.xp
                current_stats.level = updated_stats.level
                current_stats.messages_count = updated_stats.messages_count
                current_stats.links_shared = updated_stats.links_shared
                current_stats.thanks_received = updated_stats.thanks_received
            
            # Reset mock for next call
            self.mock_user_stats_repo.reset_mock()
        
        # Journey steps
        # 1. First message
        await process_and_update("Hello everyone!")
        self.assertEqual(current_stats.xp, 1)
        self.assertEqual(current_stats.messages_count, 1)
        
        # 2. Message with link
        await process_and_update("Check out https://example.com")
        self.assertEqual(current_stats.xp, 5)  # 1 + 4 (1 message + 3 link)
        self.assertEqual(current_stats.links_shared, 1)
        
        # 3. Multiple regular messages to build up XP
        for i in range(45):  # 45 more messages to reach level 2
            await process_and_update(f"Regular message {i}")
        
        # Should be at level 2 now (50 XP)
        self.assertEqual(current_stats.level, 2)
        self.assertEqual(current_stats.xp, 50)
        
        # 4. Continue to level 3
        for i in range(50):  # 50 more messages to reach level 3 (100 XP)
            await process_and_update(f"More messages {i}")
        
        self.assertEqual(current_stats.level, 3)
        self.assertEqual(current_stats.xp, 100)
    
    @pytest.mark.asyncio
    async def test_group_interaction_simulation(self):
        """Test simulation of group interactions with multiple users."""
        context = self.create_mock_context()
        
        # Create multiple users
        users = [
            {"id": 12345, "username": "alice"},
            {"id": 12346, "username": "bob"},
            {"id": 12347, "username": "charlie"}
        ]
        
        # Track user stats
        user_stats = {}
        for user in users:
            user_stats[user["id"]] = UserStats(
                user_id=user["id"],
                chat_id=-1001234567890,
                xp=0,
                level=1,
                messages_count=0,
                links_shared=0,
                thanks_received=0
            )
        
        # Mock get_user_stats to return appropriate stats
        def mock_get_user_stats(user_id, chat_id):
            return user_stats.get(user_id)
        
        self.mock_user_stats_repo.get_user_stats.side_effect = mock_get_user_stats
        
        # Simulate group conversation
        # Alice sends a helpful message
        alice_message = self.create_telegram_message(
            "Here's a useful link: https://example.com",
            user_id=12345,
            username="alice"
        )
        await self.leveling_service.process_message(
            self.create_telegram_update(alice_message),
            context
        )
        
        # Bob thanks Alice
        bob_reply = self.create_telegram_message(
            "Thanks Alice!",
            user_id=12346,
            username="bob",
            reply_to_message=alice_message
        )
        await self.leveling_service.process_message(
            self.create_telegram_update(bob_reply),
            context
        )
        
        # Charlie also thanks Alice
        charlie_reply = self.create_telegram_message(
            "Thank you @alice!",
            user_id=12347,
            username="charlie"
        )
        
        # Mock thanked users detection for mention
        with patch.object(self.leveling_service.xp_calculator.thank_you_detector, 'get_thanked_users') as mock_thanked:
            mock_thanked.return_value = [12345]  # Alice's ID
            
            await self.leveling_service.process_message(
                self.create_telegram_update(charlie_reply),
                context
            )
        
        # Verify interactions were processed
        # Should have multiple update calls for different users
        self.assertGreater(self.mock_user_stats_repo.update_user_stats.call_count, 0)


if __name__ == '__main__':
    pytest.main([__file__, "-v"])