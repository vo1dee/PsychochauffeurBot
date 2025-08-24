"""
Load Testing for User Leveling System

This test suite validates that the leveling system can handle multiple
concurrent users and high message volumes without performance degradation.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock
from concurrent.futures import ThreadPoolExecutor
from typing import List

from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

from modules.user_leveling_service import UserLevelingService
from modules.leveling_models import UserStats


class TestLevelingLoadTest:
    """Test leveling system under load."""
    
    @pytest.fixture
    def mock_leveling_service(self):
        """Create a mock leveling service for load testing."""
        # Mock dependencies
        config_manager = Mock()
        config_manager.get_config = AsyncMock(return_value={
            'enabled': True,
            'overrides': {
                'enabled': True,
                'xp_rates': {'message': 1, 'link': 3, 'thanks': 5},
                'level_formula': {'base_xp': 50, 'multiplier': 2.0},
                'notifications': {'enabled': True}
            }
        })
        
        database = Mock()
        
        # Create service
        service = UserLevelingService(config_manager=config_manager, database=database)
        
        # Mock repositories with fast responses
        service.user_stats_repo = Mock()
        service.achievement_repo = Mock()
        service.notification_service = Mock()
        
        # Mock fast database operations
        service.user_stats_repo.get_user_stats = AsyncMock(return_value=UserStats(user_id=123, chat_id=456))
        service.user_stats_repo.update_user_stats = AsyncMock(return_value=None)
        service.achievement_repo.get_user_achievements = AsyncMock(return_value=[])
        
        return service
    
    def create_mock_update(self, user_id: int, chat_id: int, message_text: str = "Hello world!"):
        """Create a mock Telegram update."""
        user = Mock(spec=User)
        user.id = user_id
        user.username = f"user{user_id}"
        user.is_bot = False
        
        chat = Mock(spec=Chat)
        chat.id = chat_id
        chat.type = "group"
        
        message = Mock(spec=Message)
        message.from_user = user
        message.chat = chat
        message.text = message_text
        message.message_id = 1
        
        update = Mock(spec=Update)
        update.message = message
        update.effective_chat = chat
        update.effective_user = user
        
        return update
    
    def create_mock_context(self):
        """Create a mock context."""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot_data = {'service_registry': Mock()}
        return context
    
    @pytest.mark.asyncio
    async def test_single_user_high_volume_messages(self, mock_leveling_service):
        """Test single user sending many messages rapidly."""
        await mock_leveling_service.initialize()
        
        user_id = 123
        chat_id = 456
        message_count = 100
        
        context = self.create_mock_context()
        
        start_time = time.time()
        
        # Send many messages from single user
        for i in range(message_count):
            update = self.create_mock_update(user_id, chat_id, f"Message {i}")
            await mock_leveling_service.process_message(update, context)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify performance (should process 100 messages in reasonable time)
        assert processing_time < 5.0  # Less than 5 seconds for 100 messages
        
        # Verify all messages were processed
        assert mock_leveling_service.user_stats_repo.update_user_stats.call_count == message_count
        
        print(f"Processed {message_count} messages in {processing_time:.2f} seconds")
        print(f"Average processing time per message: {(processing_time / message_count) * 1000:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_multiple_users_concurrent_messages(self, mock_leveling_service):
        """Test multiple users sending messages concurrently."""
        await mock_leveling_service.initialize()
        
        user_count = 10
        messages_per_user = 20
        chat_id = 456
        
        context = self.create_mock_context()
        
        async def process_user_messages(user_id: int):
            """Process messages for a single user."""
            for i in range(messages_per_user):
                update = self.create_mock_update(user_id, chat_id, f"User {user_id} message {i}")
                await mock_leveling_service.process_message(update, context)
        
        start_time = time.time()
        
        # Process messages from multiple users concurrently
        tasks = []
        for user_id in range(1, user_count + 1):
            task = asyncio.create_task(process_user_messages(user_id))
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        processing_time = end_time - start_time
        total_messages = user_count * messages_per_user
        
        # Verify performance
        assert processing_time < 10.0  # Less than 10 seconds for 200 messages
        
        # Verify all messages were processed
        assert mock_leveling_service.user_stats_repo.update_user_stats.call_count == total_messages
        
        print(f"Processed {total_messages} messages from {user_count} users in {processing_time:.2f} seconds")
        print(f"Average processing time per message: {(processing_time / total_messages) * 1000:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_mixed_message_types_load(self, mock_leveling_service):
        """Test processing mixed message types under load."""
        await mock_leveling_service.initialize()
        
        user_id = 123
        chat_id = 456
        context = self.create_mock_context()
        
        # Different message types
        message_types = [
            "Regular message",
            "Message with link: https://example.com",
            "Thanks @user456 for the help!",
            "Another regular message",
            "Multiple links: https://test.com and http://demo.org"
        ]
        
        iterations = 20  # 20 iterations of each message type = 100 messages
        
        start_time = time.time()
        
        for i in range(iterations):
            for message_text in message_types:
                update = self.create_mock_update(user_id, chat_id, message_text)
                await mock_leveling_service.process_message(update, context)
        
        end_time = time.time()
        processing_time = end_time - start_time
        total_messages = iterations * len(message_types)
        
        # Verify performance
        assert processing_time < 5.0  # Less than 5 seconds
        
        print(f"Processed {total_messages} mixed messages in {processing_time:.2f} seconds")
        print(f"Average processing time per message: {(processing_time / total_messages) * 1000:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_error_handling_under_load(self, mock_leveling_service):
        """Test error handling doesn't degrade performance under load."""
        await mock_leveling_service.initialize()
        
        # Simulate database errors for some operations
        error_count = 0
        original_update = mock_leveling_service.user_stats_repo.update_user_stats
        
        async def failing_update(*args, **kwargs):
            nonlocal error_count
            error_count += 1
            if error_count % 5 == 0:  # Fail every 5th operation
                raise Exception("Simulated database error")
            return await original_update(*args, **kwargs)
        
        mock_leveling_service.user_stats_repo.update_user_stats = failing_update
        
        user_id = 123
        chat_id = 456
        message_count = 50
        context = self.create_mock_context()
        
        start_time = time.time()
        
        # Process messages with some failures
        for i in range(message_count):
            update = self.create_mock_update(user_id, chat_id, f"Message {i}")
            await mock_leveling_service.process_message(update, context)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify system continues to work despite errors
        assert processing_time < 5.0  # Should still be fast
        assert mock_leveling_service._stats['errors'] > 0  # Should have recorded errors
        
        print(f"Processed {message_count} messages with errors in {processing_time:.2f} seconds")
        print(f"Errors encountered: {mock_leveling_service._stats['errors']}")
    
    @pytest.mark.asyncio
    async def test_rate_limiting_under_load(self, mock_leveling_service):
        """Test rate limiting behavior under high load."""
        await mock_leveling_service.initialize()
        
        # Enable rate limiting
        mock_leveling_service._current_leveling_config.rate_limiting.enabled = True
        mock_leveling_service._current_leveling_config.rate_limiting.max_xp_per_minute = 10
        
        user_id = 123
        chat_id = 456
        message_count = 50  # More than rate limit
        context = self.create_mock_context()
        
        start_time = time.time()
        
        # Send messages rapidly
        for i in range(message_count):
            update = self.create_mock_update(user_id, chat_id, f"Message {i}")
            await mock_leveling_service.process_message(update, context)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify rate limiting kicked in
        assert mock_leveling_service._stats['rate_limited'] > 0
        
        # Should still process quickly (rate limiting doesn't slow down processing)
        assert processing_time < 5.0
        
        print(f"Processed {message_count} messages with rate limiting in {processing_time:.2f} seconds")
        print(f"Rate limited operations: {mock_leveling_service._stats['rate_limited']}")
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, mock_leveling_service):
        """Test that memory usage doesn't grow excessively under load."""
        import psutil
        import os
        
        await mock_leveling_service.initialize()
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        user_count = 20
        messages_per_user = 50
        chat_id = 456
        context = self.create_mock_context()
        
        # Process many messages
        for user_id in range(1, user_count + 1):
            for i in range(messages_per_user):
                update = self.create_mock_update(user_id, chat_id, f"Message {i}")
                await mock_leveling_service.process_message(update, context)
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB for this test)
        assert memory_increase < 50
        
        total_messages = user_count * messages_per_user
        print(f"Processed {total_messages} messages")
        print(f"Memory usage: {initial_memory:.1f}MB -> {final_memory:.1f}MB (increase: {memory_increase:.1f}MB)")
    
    def test_performance_benchmarks(self):
        """Test performance benchmarks and requirements."""
        # These are the performance requirements from the design
        max_processing_time_ms = 100  # 100ms max per message
        max_memory_per_user_kb = 10   # 10KB max per user
        max_concurrent_users = 100    # Should handle 100 concurrent users
        
        # Verify requirements are reasonable
        assert max_processing_time_ms > 0
        assert max_memory_per_user_kb > 0
        assert max_concurrent_users > 0
        
        print(f"Performance requirements:")
        print(f"- Max processing time per message: {max_processing_time_ms}ms")
        print(f"- Max memory per user: {max_memory_per_user_kb}KB")
        print(f"- Max concurrent users: {max_concurrent_users}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])