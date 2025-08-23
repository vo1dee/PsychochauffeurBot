"""
Performance tests for the User Leveling System.

This module tests the leveling system's performance under high-volume message
scenarios, stress testing, and load conditions to ensure it meets performance
requirements and scales appropriately.
"""

import pytest
import asyncio
import time
import statistics
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from telegram import Update, Message, User, Chat, Bot
from telegram.ext import ContextTypes

# Import leveling system components
from modules.user_leveling_service import UserLevelingService
from modules.xp_calculator import XPCalculator
from modules.level_manager import LevelManager
from modules.achievement_engine import AchievementEngine
from modules.leveling_models import UserStats, Achievement
from modules.repositories import UserStatsRepository, AchievementRepository

# Import test base classes
from tests.base_test_classes import AsyncBaseTestCase


class TestLevelingSystemPerformance(AsyncBaseTestCase):
    """Performance tests for the leveling system."""
    
    async def setUp(self):
        """Set up performance test environment."""
        await super().setUp()
        
        # Create mock dependencies with optimized responses
        self.mock_config_manager = Mock()
        self.mock_config_manager.get.return_value = {
            'enabled': True,
            'level_base_xp': 50,
            'level_multiplier': 2.0,
            'notifications_enabled': False,  # Disable for performance testing
            'xp_rates': {'message': 1, 'link': 3, 'thanks': 5}
        }
        
        self.mock_database = AsyncMock()
        
        # Create leveling service
        self.leveling_service = UserLevelingService(
            config_manager=self.mock_config_manager,
            database=self.mock_database
        )
        
        # Mock repositories with fast responses
        self.mock_user_stats_repo = AsyncMock(spec=UserStatsRepository)
        self.mock_achievement_repo = AsyncMock(spec=AchievementRepository)
        self.mock_notification_service = AsyncMock()
        
        # Initialize service
        with patch('modules.user_leveling_service.UserStatsRepository', return_value=self.mock_user_stats_repo), \
             patch('modules.user_leveling_service.AchievementRepository', return_value=self.mock_achievement_repo), \
             patch('modules.user_leveling_service.LevelingNotificationService', return_value=self.mock_notification_service):
            await self.leveling_service.initialize()
        
        # Performance tracking
        self.performance_metrics = {
            'processing_times': [],
            'memory_usage': [],
            'database_calls': 0,
            'errors': 0
        }
    
    async def tearDown(self):
        """Clean up performance test environment."""
        if hasattr(self, 'leveling_service'):
            await self.leveling_service.shutdown()
        await super().tearDown()
    
    def create_test_message(self, text: str, user_id: int = 12345, chat_id: int = -1001234567890) -> Message:
        """Create a test message for performance testing."""
        user = User(id=user_id, is_bot=False, first_name="Test", username=f"user{user_id}")
        chat = Chat(id=chat_id, type=Chat.SUPERGROUP, title="Test Group")
        
        return Message(
            message_id=1,
            date=datetime.now(),
            chat=chat,
            from_user=user,
            text=text
        )
    
    def create_test_update(self, message: Message) -> Update:
        """Create a test update for performance testing."""
        return Update(update_id=1, message=message)
    
    def create_mock_context(self) -> Mock:
        """Create a mock context for performance testing."""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = Mock(spec=Bot)
        context.bot.send_message = AsyncMock()
        return context
    
    async def measure_processing_time(self, coro):
        """Measure the processing time of a coroutine."""
        start_time = time.perf_counter()
        try:
            result = await coro
            success = True
        except Exception as e:
            result = e
            success = False
            self.performance_metrics['errors'] += 1
        
        end_time = time.perf_counter()
        processing_time = end_time - start_time
        self.performance_metrics['processing_times'].append(processing_time)
        
        return result, processing_time, success


class TestSingleMessagePerformance(TestLevelingSystemPerformance):
    """Test performance of single message processing."""
    
    @pytest.mark.asyncio
    async def test_simple_message_processing_time(self):
        """Test processing time for simple messages."""
        # Mock fast database responses
        self.mock_user_stats_repo.get_user_stats.return_value = UserStats(
            user_id=12345, chat_id=-1001234567890, xp=10, level=1
        )
        self.mock_user_stats_repo.update_user_stats.return_value = None
        
        # Create test message
        message = self.create_test_message("Hello world!")
        update = self.create_test_update(message)
        context = self.create_mock_context()
        
        # Measure processing time
        result, processing_time, success = await self.measure_processing_time(
            self.leveling_service.process_message(update, context)
        )
        
        # Verify performance requirements
        self.assertTrue(success, f"Message processing failed: {result}")
        self.assertLess(processing_time, 0.1, f"Processing took {processing_time:.3f}s, expected < 0.1s")
    
    @pytest.mark.asyncio
    async def test_complex_message_processing_time(self):
        """Test processing time for complex messages with links and thanks."""
        # Mock database responses
        sender_stats = UserStats(user_id=12345, chat_id=-1001234567890, xp=10, level=1)
        thanked_stats = UserStats(user_id=54321, chat_id=-1001234567890, xp=20, level=1)
        
        def mock_get_user_stats(user_id, chat_id):
            if user_id == 12345:
                return sender_stats
            elif user_id == 54321:
                return thanked_stats
            return None
        
        self.mock_user_stats_repo.get_user_stats.side_effect = mock_get_user_stats
        self.mock_user_stats_repo.update_user_stats.return_value = None
        
        # Create complex message
        reply_message = self.create_test_message("Original message", user_id=54321)
        message = self.create_test_message(
            "Thanks! Check https://example.com and http://test.org",
            reply_to_message=reply_message
        )
        update = self.create_test_update(message)
        context = self.create_mock_context()
        
        # Measure processing time
        result, processing_time, success = await self.measure_processing_time(
            self.leveling_service.process_message(update, context)
        )
        
        # Verify performance requirements
        self.assertTrue(success, f"Complex message processing failed: {result}")
        self.assertLess(processing_time, 0.1, f"Complex processing took {processing_time:.3f}s, expected < 0.1s")
    
    @pytest.mark.asyncio
    async def test_new_user_creation_performance(self):
        """Test performance when creating new users."""
        # Mock new user scenario
        self.mock_user_stats_repo.get_user_stats.return_value = None
        self.mock_user_stats_repo.create_user_stats.return_value = UserStats(
            user_id=12345, chat_id=-1001234567890, xp=0, level=1
        )
        self.mock_user_stats_repo.update_user_stats.return_value = None
        
        # Create test message
        message = self.create_test_message("First message!")
        update = self.create_test_update(message)
        context = self.create_mock_context()
        
        # Measure processing time
        result, processing_time, success = await self.measure_processing_time(
            self.leveling_service.process_message(update, context)
        )
        
        # Verify performance requirements
        self.assertTrue(success, f"New user creation failed: {result}")
        self.assertLess(processing_time, 0.15, f"New user creation took {processing_time:.3f}s, expected < 0.15s")


class TestHighVolumePerformance(TestLevelingSystemPerformance):
    """Test performance under high message volume."""
    
    @pytest.mark.asyncio
    async def test_sequential_message_processing(self):
        """Test processing many messages sequentially."""
        # Mock database responses
        self.mock_user_stats_repo.get_user_stats.return_value = UserStats(
            user_id=12345, chat_id=-1001234567890, xp=10, level=1
        )
        self.mock_user_stats_repo.update_user_stats.return_value = None
        
        context = self.create_mock_context()
        message_count = 100
        
        # Process messages sequentially
        start_time = time.perf_counter()
        
        for i in range(message_count):
            message = self.create_test_message(f"Message {i}")
            update = self.create_test_update(message)
            
            result, processing_time, success = await self.measure_processing_time(
                self.leveling_service.process_message(update, context)
            )
            
            self.assertTrue(success, f"Message {i} processing failed: {result}")
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Verify performance requirements
        avg_processing_time = statistics.mean(self.performance_metrics['processing_times'])
        max_processing_time = max(self.performance_metrics['processing_times'])
        
        self.assertLess(avg_processing_time, 0.05, f"Average processing time {avg_processing_time:.3f}s too high")
        self.assertLess(max_processing_time, 0.2, f"Max processing time {max_processing_time:.3f}s too high")
        self.assertLess(total_time, 10.0, f"Total time {total_time:.3f}s for {message_count} messages too high")
        
        print(f"Sequential processing: {message_count} messages in {total_time:.3f}s")
        print(f"Average: {avg_processing_time:.3f}s, Max: {max_processing_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self):
        """Test processing many messages concurrently."""
        # Mock database responses
        self.mock_user_stats_repo.get_user_stats.return_value = UserStats(
            user_id=12345, chat_id=-1001234567890, xp=10, level=1
        )
        self.mock_user_stats_repo.update_user_stats.return_value = None
        
        context = self.create_mock_context()
        message_count = 50  # Reduced for concurrent testing
        
        # Create all messages
        messages = [
            self.create_test_message(f"Concurrent message {i}")
            for i in range(message_count)
        ]
        updates = [self.create_test_update(msg) for msg in messages]
        
        # Process messages concurrently
        start_time = time.perf_counter()
        
        tasks = [
            self.measure_processing_time(
                self.leveling_service.process_message(update, context)
            )
            for update in updates
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Verify all messages were processed successfully
        successful_results = [r for r in results if not isinstance(r, Exception) and r[2]]
        self.assertEqual(len(successful_results), message_count, "Not all messages processed successfully")
        
        # Verify performance requirements
        processing_times = [r[1] for r in successful_results]
        avg_processing_time = statistics.mean(processing_times)
        max_processing_time = max(processing_times)
        
        self.assertLess(avg_processing_time, 0.1, f"Average concurrent processing time {avg_processing_time:.3f}s too high")
        self.assertLess(total_time, 5.0, f"Total concurrent time {total_time:.3f}s for {message_count} messages too high")
        
        print(f"Concurrent processing: {message_count} messages in {total_time:.3f}s")
        print(f"Average: {avg_processing_time:.3f}s, Max: {max_processing_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_mixed_user_concurrent_processing(self):
        """Test concurrent processing with multiple users."""
        # Mock database responses for multiple users
        def mock_get_user_stats(user_id, chat_id):
            return UserStats(user_id=user_id, chat_id=chat_id, xp=10, level=1)
        
        self.mock_user_stats_repo.get_user_stats.side_effect = mock_get_user_stats
        self.mock_user_stats_repo.update_user_stats.return_value = None
        
        context = self.create_mock_context()
        user_count = 10
        messages_per_user = 5
        
        # Create messages from multiple users
        all_updates = []
        for user_id in range(12345, 12345 + user_count):
            for msg_id in range(messages_per_user):
                message = self.create_test_message(f"Message {msg_id} from user {user_id}", user_id=user_id)
                update = self.create_test_update(message)
                all_updates.append(update)
        
        # Process all messages concurrently
        start_time = time.perf_counter()
        
        tasks = [
            self.measure_processing_time(
                self.leveling_service.process_message(update, context)
            )
            for update in all_updates
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        total_messages = user_count * messages_per_user
        
        # Verify results
        successful_results = [r for r in results if not isinstance(r, Exception) and r[2]]
        self.assertEqual(len(successful_results), total_messages, "Not all messages processed successfully")
        
        # Verify performance
        processing_times = [r[1] for r in successful_results]
        avg_processing_time = statistics.mean(processing_times)
        
        self.assertLess(avg_processing_time, 0.1, f"Average multi-user processing time {avg_processing_time:.3f}s too high")
        self.assertLess(total_time, 10.0, f"Total multi-user time {total_time:.3f}s too high")
        
        print(f"Multi-user processing: {total_messages} messages from {user_count} users in {total_time:.3f}s")
        print(f"Average: {avg_processing_time:.3f}s per message")


class TestComponentPerformance(TestLevelingSystemPerformance):
    """Test performance of individual components."""
    
    def test_xp_calculator_performance(self):
        """Test XP calculator performance with various message types."""
        calculator = XPCalculator()
        
        # Test messages
        test_messages = [
            "Simple message",
            "Message with link https://example.com",
            "Multiple links: https://example.com http://test.org https://another.com",
            "Long message " + "word " * 1000,
            "Thanks @user for the help!",
            "Complex: Thanks @user! Check https://example.com and http://test.org for more info!"
        ]
        
        # Create message mocks
        message_mocks = []
        for text in test_messages:
            message = Mock()
            message.text = text
            message.from_user = Mock()
            message.from_user.id = 12345
            message.from_user.is_bot = False
            message.reply_to_message = None
            message_mocks.append(message)
        
        # Measure performance
        iterations = 1000
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            for message in message_mocks:
                sender_xp, thanked_xp = calculator.calculate_total_message_xp(message)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        avg_time_per_calculation = total_time / (iterations * len(test_messages))
        
        # Verify performance requirements
        self.assertLess(avg_time_per_calculation, 0.001, 
                       f"XP calculation too slow: {avg_time_per_calculation:.6f}s per message")
        
        print(f"XP Calculator: {iterations * len(test_messages)} calculations in {total_time:.3f}s")
        print(f"Average: {avg_time_per_calculation:.6f}s per calculation")
    
    def test_level_manager_performance(self):
        """Test level manager performance with various XP values."""
        level_manager = LevelManager()
        
        # Test XP values
        xp_values = list(range(0, 100000, 100)) + [1000000, 5000000, 10000000]
        
        # Measure level calculation performance
        iterations = 100
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            for xp in xp_values:
                level = level_manager.calculate_level(xp)
                self.assertGreaterEqual(level, 1)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        avg_time_per_calculation = total_time / (iterations * len(xp_values))
        
        # Verify performance requirements
        self.assertLess(avg_time_per_calculation, 0.0001,
                       f"Level calculation too slow: {avg_time_per_calculation:.6f}s per calculation")
        
        print(f"Level Manager: {iterations * len(xp_values)} calculations in {total_time:.3f}s")
        print(f"Average: {avg_time_per_calculation:.6f}s per calculation")
    
    def test_level_manager_threshold_caching(self):
        """Test level manager threshold caching performance."""
        level_manager = LevelManager()
        
        # Test levels
        levels = list(range(1, 101))  # Levels 1-100
        
        # First pass - populate cache
        start_time = time.perf_counter()
        for level in levels:
            threshold = level_manager.get_level_threshold(level)
            self.assertGreaterEqual(threshold, 0)
        first_pass_time = time.perf_counter() - start_time
        
        # Second pass - use cache
        start_time = time.perf_counter()
        for level in levels:
            threshold = level_manager.get_level_threshold(level)
            self.assertGreaterEqual(threshold, 0)
        second_pass_time = time.perf_counter() - start_time
        
        # Cache should make second pass significantly faster
        self.assertLess(second_pass_time, first_pass_time * 0.5,
                       "Caching not providing expected performance improvement")
        
        print(f"Level thresholds: First pass {first_pass_time:.3f}s, Second pass {second_pass_time:.3f}s")
        print(f"Cache speedup: {first_pass_time / second_pass_time:.1f}x")


class TestMemoryPerformance(TestLevelingSystemPerformance):
    """Test memory usage and performance under load."""
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """Test memory usage doesn't grow excessively under load."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Mock database responses
        self.mock_user_stats_repo.get_user_stats.return_value = UserStats(
            user_id=12345, chat_id=-1001234567890, xp=10, level=1
        )
        self.mock_user_stats_repo.update_user_stats.return_value = None
        
        context = self.create_mock_context()
        
        # Process many messages
        message_count = 500
        for i in range(message_count):
            message = self.create_test_message(f"Memory test message {i}")
            update = self.create_test_update(message)
            
            await self.leveling_service.process_message(update, context)
            
            # Check memory every 100 messages
            if i % 100 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_growth = current_memory - initial_memory
                
                # Memory growth should be reasonable
                self.assertLess(memory_growth, 50, f"Excessive memory growth: {memory_growth:.1f}MB after {i} messages")
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_growth = final_memory - initial_memory
        
        print(f"Memory usage: Initial {initial_memory:.1f}MB, Final {final_memory:.1f}MB")
        print(f"Memory growth: {total_memory_growth:.1f}MB for {message_count} messages")
        
        # Total memory growth should be reasonable
        self.assertLess(total_memory_growth, 100, f"Excessive total memory growth: {total_memory_growth:.1f}MB")
    
    @pytest.mark.asyncio
    async def test_no_memory_leaks(self):
        """Test for memory leaks in repeated operations."""
        import gc
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Mock database responses
        self.mock_user_stats_repo.get_user_stats.return_value = UserStats(
            user_id=12345, chat_id=-1001234567890, xp=10, level=1
        )
        self.mock_user_stats_repo.update_user_stats.return_value = None
        
        context = self.create_mock_context()
        
        # Perform multiple cycles of message processing
        cycles = 5
        messages_per_cycle = 100
        memory_readings = []
        
        for cycle in range(cycles):
            # Process messages
            for i in range(messages_per_cycle):
                message = self.create_test_message(f"Leak test cycle {cycle} message {i}")
                update = self.create_test_update(message)
                await self.leveling_service.process_message(update, context)
            
            # Force garbage collection
            gc.collect()
            
            # Record memory usage
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_readings.append(memory_mb)
            
            print(f"Cycle {cycle + 1}: {memory_mb:.1f}MB")
        
        # Check for consistent memory growth (indicating leaks)
        if len(memory_readings) >= 3:
            # Calculate trend
            memory_growth_per_cycle = (memory_readings[-1] - memory_readings[0]) / (cycles - 1)
            
            # Memory growth per cycle should be minimal
            self.assertLess(memory_growth_per_cycle, 5.0,
                           f"Potential memory leak: {memory_growth_per_cycle:.1f}MB growth per cycle")
        
        print(f"Memory leak test: {cycles} cycles of {messages_per_cycle} messages each")
        print(f"Memory readings: {[f'{m:.1f}MB' for m in memory_readings]}")


class TestDatabasePerformance(TestLevelingSystemPerformance):
    """Test database-related performance."""
    
    @pytest.mark.asyncio
    async def test_database_call_optimization(self):
        """Test that database calls are optimized and not excessive."""
        # Mock database responses with call counting
        get_calls = 0
        update_calls = 0
        
        async def mock_get_user_stats(user_id, chat_id):
            nonlocal get_calls
            get_calls += 1
            return UserStats(user_id=user_id, chat_id=chat_id, xp=10, level=1)
        
        async def mock_update_user_stats(stats):
            nonlocal update_calls
            update_calls += 1
        
        self.mock_user_stats_repo.get_user_stats.side_effect = mock_get_user_stats
        self.mock_user_stats_repo.update_user_stats.side_effect = mock_update_user_stats
        
        context = self.create_mock_context()
        message_count = 50
        
        # Process messages
        for i in range(message_count):
            message = self.create_test_message(f"DB optimization test {i}")
            update = self.create_test_update(message)
            await self.leveling_service.process_message(update, context)
        
        # Verify database call efficiency
        # Should be 1 get and 1 update per message (assuming no caching)
        self.assertEqual(get_calls, message_count, f"Expected {message_count} get calls, got {get_calls}")
        self.assertEqual(update_calls, message_count, f"Expected {message_count} update calls, got {update_calls}")
        
        print(f"Database calls for {message_count} messages: {get_calls} gets, {update_calls} updates")
    
    @pytest.mark.asyncio
    async def test_database_error_recovery_performance(self):
        """Test performance when recovering from database errors."""
        # Mock database with intermittent failures
        call_count = 0
        
        async def mock_get_user_stats_with_failures(user_id, chat_id):
            nonlocal call_count
            call_count += 1
            
            # Fail every 5th call
            if call_count % 5 == 0:
                raise Exception("Simulated database error")
            
            return UserStats(user_id=user_id, chat_id=chat_id, xp=10, level=1)
        
        self.mock_user_stats_repo.get_user_stats.side_effect = mock_get_user_stats_with_failures
        self.mock_user_stats_repo.update_user_stats.return_value = None
        
        context = self.create_mock_context()
        message_count = 20
        
        # Process messages with intermittent failures
        start_time = time.perf_counter()
        
        for i in range(message_count):
            message = self.create_test_message(f"Error recovery test {i}")
            update = self.create_test_update(message)
            
            # Should handle errors gracefully without crashing
            try:
                await self.leveling_service.process_message(update, context)
            except Exception as e:
                # Some failures are expected, but service should remain operational
                pass
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Even with errors, processing should complete in reasonable time
        self.assertLess(total_time, 5.0, f"Error recovery too slow: {total_time:.3f}s for {message_count} messages")
        
        print(f"Error recovery test: {message_count} messages with failures in {total_time:.3f}s")


if __name__ == '__main__':
    pytest.main([__file__, "-v", "--tb=short"])