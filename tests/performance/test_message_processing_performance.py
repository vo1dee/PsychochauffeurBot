"""
Performance tests for critical message processing paths.
Tests message handling performance under various load conditions.
"""

import asyncio
import time
import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, User, Chat
from telegram.ext import CallbackContext

from modules.message_handler_service import MessageHandlerService
from modules.speech_recognition_service import SpeechRecognitionService
from modules.callback_handler_service import CallbackHandlerService
from modules.command_registry import CommandRegistry
from modules.command_processor import CommandProcessor
from config.config_manager import ConfigManager


class TestMessageProcessingPerformance:
    """Performance tests for message processing components."""

    @pytest.fixture
    async def mock_config_manager(self):
        """Create a mock config manager for performance tests."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock(return_value={
            'gpt': {'enabled': True, 'random_response_chance': 0.1},
            'speech': {'enabled': True, 'default_language': 'en'},
            'url_processing': {'enabled': True}
        })
        return config_manager

    @pytest.fixture
    async def message_handler_service(self, mock_config_manager):
        """Create message handler service for performance testing."""
        gpt_service = Mock()
        gpt_service.should_respond_randomly = AsyncMock(return_value=False)
        gpt_service.process_message = AsyncMock(return_value="Test response")
        
        service = MessageHandlerService(
            config_manager=mock_config_manager,
            gpt_service=gpt_service
        )
        return service

    @pytest.fixture
    async def speech_service(self, mock_config_manager):
        """Create speech recognition service for performance testing."""
        service = SpeechRecognitionService(config_manager=mock_config_manager)
        return service

    @pytest.fixture
    async def callback_service(self, speech_service):
        """Create callback handler service for performance testing."""
        service = CallbackHandlerService(speech_service=speech_service)
        return service

    @pytest.fixture
    async def command_registry(self):
        """Create command registry for performance testing."""
        command_processor = Mock(spec=CommandProcessor)
        registry = CommandRegistry(command_processor=command_processor)
        return registry

    def create_mock_update(self, text="Test message", user_id=12345, chat_id=67890):
        """Create a mock Telegram update for testing."""
        user = Mock(spec=User)
        user.id = user_id
        user.first_name = "Test"
        user.username = "testuser"

        chat = Mock(spec=Chat)
        chat.id = chat_id
        chat.type = "private"

        message = Mock(spec=Message)
        message.text = text
        message.from_user = user
        message.chat = chat
        message.message_id = 1

        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat

        return update

    @pytest.mark.asyncio
    async def test_message_handler_throughput(self, message_handler_service):
        """Test message handler throughput under load."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Test processing 100 messages
        message_count = 100
        start_time = time.time()
        
        tasks = []
        for i in range(message_count):
            update = self.create_mock_update(f"Test message {i}")
            task = message_handler_service.handle_text_message(update, context)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        throughput = message_count / duration
        
        # Should process at least 50 messages per second
        assert throughput > 50, f"Throughput too low: {throughput:.2f} msg/sec"
        print(f"Message handler throughput: {throughput:.2f} messages/second")

    @pytest.mark.asyncio
    async def test_speech_service_performance(self, speech_service):
        """Test speech recognition service performance."""
        # Test configuration retrieval performance
        chat_id = "test_chat"
        chat_type = "group"
        
        start_time = time.time()
        
        # Test 50 concurrent configuration requests
        tasks = []
        for _ in range(50):
            task = speech_service.get_speech_config(chat_id, chat_type)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within 1 second
        assert duration < 1.0, f"Speech config retrieval too slow: {duration:.2f}s"
        
        # All requests should succeed
        successful_requests = sum(1 for r in results if not isinstance(r, Exception))
        assert successful_requests == 50, f"Only {successful_requests}/50 requests succeeded"
        
        print(f"Speech config retrieval: {duration:.3f}s for 50 requests")

    @pytest.mark.asyncio
    async def test_callback_handler_performance(self, callback_service):
        """Test callback handler performance under load."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Create mock callback query
        callback_query = Mock()
        callback_query.data = "speech_lang_en_abc123"
        callback_query.answer = AsyncMock()
        
        update = Mock(spec=Update)
        update.callback_query = callback_query
        
        start_time = time.time()
        
        # Test 100 concurrent callback processing
        tasks = []
        for _ in range(100):
            task = callback_service.handle_callback_query(update, context)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        throughput = 100 / duration
        
        # Should process at least 100 callbacks per second
        assert throughput > 100, f"Callback throughput too low: {throughput:.2f} callbacks/sec"
        print(f"Callback handler throughput: {throughput:.2f} callbacks/second")

    @pytest.mark.asyncio
    async def test_command_registry_performance(self, command_registry):
        """Test command registry performance."""
        # Test command registration performance
        start_time = time.time()
        
        await command_registry.register_all_commands()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Command registration should complete quickly
        assert duration < 0.5, f"Command registration too slow: {duration:.2f}s"
        print(f"Command registration time: {duration:.3f}s")

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, message_handler_service):
        """Test concurrent message processing with different message types."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Create different types of messages
        text_updates = [self.create_mock_update(f"Text {i}") for i in range(50)]
        url_updates = [self.create_mock_update(f"Check this out: https://example.com/{i}") for i in range(25)]
        command_updates = [self.create_mock_update(f"/test{i}") for i in range(25)]
        
        all_updates = text_updates + url_updates + command_updates
        
        start_time = time.time()
        
        # Process all messages concurrently
        tasks = []
        for update in all_updates:
            task = message_handler_service.handle_text_message(update, context)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        throughput = len(all_updates) / duration
        
        # Should handle mixed message types efficiently
        assert throughput > 30, f"Mixed message throughput too low: {throughput:.2f} msg/sec"
        
        # Most messages should process successfully
        successful = sum(1 for r in results if not isinstance(r, Exception))
        success_rate = successful / len(all_updates)
        assert success_rate > 0.9, f"Success rate too low: {success_rate:.2%}"
        
        print(f"Mixed message processing: {throughput:.2f} msg/sec, {success_rate:.2%} success rate")

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, message_handler_service):
        """Test memory usage during high-load message processing."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Process a large number of messages
        message_count = 500
        batch_size = 50
        
        for batch in range(0, message_count, batch_size):
            tasks = []
            for i in range(batch, min(batch + batch_size, message_count)):
                update = self.create_mock_update(f"Memory test message {i}")
                task = message_handler_service.handle_text_message(update, context)
                tasks.append(task)
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check memory usage periodically
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            # Memory increase should be reasonable (less than 100MB)
            assert memory_increase < 100, f"Memory usage increased by {memory_increase:.2f}MB"
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - initial_memory
        
        print(f"Memory usage: {initial_memory:.2f}MB -> {final_memory:.2f}MB (+{total_increase:.2f}MB)")

    @pytest.mark.asyncio
    async def test_error_handling_performance(self, message_handler_service):
        """Test performance when handling errors."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Mock GPT service to raise exceptions
        message_handler_service.gpt_service.process_message = AsyncMock(
            side_effect=Exception("Simulated error")
        )
        
        start_time = time.time()
        
        # Process messages that will cause errors
        tasks = []
        for i in range(100):
            update = self.create_mock_update(f"Error test {i}")
            task = message_handler_service.handle_text_message(update, context)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        throughput = 100 / duration
        
        # Error handling should still be reasonably fast
        assert throughput > 20, f"Error handling throughput too low: {throughput:.2f} msg/sec"
        
        # All should complete (even with errors)
        assert len(results) == 100, "Not all error cases completed"
        
        print(f"Error handling throughput: {throughput:.2f} messages/second")

    @pytest.mark.asyncio
    async def test_service_initialization_performance(self):
        """Test service initialization performance."""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_config = AsyncMock(return_value={})
        
        start_time = time.time()
        
        # Initialize multiple services
        services = []
        for _ in range(10):
            message_service = MessageHandlerService(
                config_manager=mock_config,
                gpt_service=Mock()
            )
            speech_service = SpeechRecognitionService(config_manager=mock_config)
            callback_service = CallbackHandlerService(speech_service=speech_service)
            
            services.extend([message_service, speech_service, callback_service])
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Service initialization should be fast
        assert duration < 1.0, f"Service initialization too slow: {duration:.2f}s"
        assert len(services) == 30, "Not all services initialized"
        
        print(f"Service initialization: {duration:.3f}s for 30 services")


class TestComponentIntegrationPerformance:
    """Performance tests for component integration scenarios."""

    @pytest.fixture
    async def integrated_services(self):
        """Create integrated services for performance testing."""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_config = AsyncMock(return_value={
            'gpt': {'enabled': True},
            'speech': {'enabled': True},
            'commands': {'enabled': True}
        })
        
        # Create integrated services
        gpt_service = Mock()
        gpt_service.process_message = AsyncMock(return_value="Response")
        
        message_service = MessageHandlerService(
            config_manager=mock_config,
            gpt_service=gpt_service
        )
        
        speech_service = SpeechRecognitionService(config_manager=mock_config)
        callback_service = CallbackHandlerService(speech_service=speech_service)
        
        command_processor = Mock(spec=CommandProcessor)
        command_registry = CommandRegistry(command_processor=command_processor)
        
        return {
            'message': message_service,
            'speech': speech_service,
            'callback': callback_service,
            'command': command_registry
        }

    @pytest.mark.asyncio
    async def test_full_pipeline_performance(self, integrated_services):
        """Test performance of full message processing pipeline."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Create various message types
        messages = [
            ("text", "Hello world"),
            ("url", "Check this: https://example.com"),
            ("command", "/help"),
            ("speech_callback", "speech_lang_en_abc123")
        ]
        
        start_time = time.time()
        
        # Process through full pipeline
        for msg_type, content in messages * 25:  # 100 total messages
            if msg_type == "speech_callback":
                # Simulate callback processing
                callback_query = Mock()
                callback_query.data = content
                callback_query.answer = AsyncMock()
                
                update = Mock(spec=Update)
                update.callback_query = callback_query
                
                await integrated_services['callback'].handle_callback_query(update, context)
            else:
                # Simulate message processing
                user = Mock(spec=User)
                user.id = 12345
                
                chat = Mock(spec=Chat)
                chat.id = 67890
                chat.type = "private"
                
                message = Mock(spec=Message)
                message.text = content
                message.from_user = user
                message.chat = chat
                
                update = Mock(spec=Update)
                update.message = message
                update.effective_user = user
                update.effective_chat = chat
                
                await integrated_services['message'].handle_text_message(update, context)
        
        end_time = time.time()
        duration = end_time - start_time
        throughput = 100 / duration
        
        # Full pipeline should maintain good throughput
        assert throughput > 25, f"Pipeline throughput too low: {throughput:.2f} msg/sec"
        print(f"Full pipeline throughput: {throughput:.2f} messages/second")

    @pytest.mark.asyncio
    async def test_concurrent_service_operations(self, integrated_services):
        """Test concurrent operations across multiple services."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        start_time = time.time()
        
        # Create concurrent tasks across all services
        tasks = []
        
        # Message processing tasks
        for i in range(25):
            update = Mock(spec=Update)
            update.message = Mock()
            update.message.text = f"Message {i}"
            update.message.from_user = Mock()
            update.message.from_user.id = 12345
            update.message.chat = Mock()
            update.message.chat.id = 67890
            update.message.chat.type = "private"
            update.effective_user = update.message.from_user
            update.effective_chat = update.message.chat
            
            task = integrated_services['message'].handle_text_message(update, context)
            tasks.append(task)
        
        # Speech config tasks
        for i in range(25):
            task = integrated_services['speech'].get_speech_config(f"chat_{i}", "group")
            tasks.append(task)
        
        # Callback processing tasks
        for i in range(25):
            callback_query = Mock()
            callback_query.data = f"speech_lang_en_{i}"
            callback_query.answer = AsyncMock()
            
            update = Mock(spec=Update)
            update.callback_query = callback_query
            
            task = integrated_services['callback'].handle_callback_query(update, context)
            tasks.append(task)
        
        # Command registry tasks
        for i in range(25):
            task = integrated_services['command'].register_all_commands()
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        throughput = len(tasks) / duration
        
        # Should handle concurrent operations efficiently
        assert throughput > 50, f"Concurrent operations throughput too low: {throughput:.2f} ops/sec"
        
        # Most operations should succeed
        successful = sum(1 for r in results if not isinstance(r, Exception))
        success_rate = successful / len(results)
        assert success_rate > 0.8, f"Success rate too low: {success_rate:.2%}"
        
        print(f"Concurrent operations: {throughput:.2f} ops/sec, {success_rate:.2%} success rate")