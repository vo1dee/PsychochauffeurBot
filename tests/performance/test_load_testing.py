"""
Load testing suite to ensure performance is maintained after refactoring.
Tests system performance under various load conditions.
"""

import asyncio
import time
import pytest
import psutil
import os
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from telegram import Update, Message, User, Chat, CallbackQuery, Voice
from telegram.ext import CallbackContext

from modules.application_bootstrapper import ApplicationBootstrapper
from modules.service_registry import ServiceRegistry


class TestLoadTesting:
    """Load testing for the refactored application."""

    @pytest.fixture
    async def load_test_application(self):
        """Set up application for load testing."""
        with patch.dict('os.environ', {
            'TELEGRAM_BOT_TOKEN': 'load_test_token_123456789',
            'ERROR_CHANNEL_ID': '-1001234567890'
        }):
            bootstrapper = ApplicationBootstrapper()
            
            with patch('modules.bot_application.Application') as mock_app_class:
                mock_app = Mock()
                mock_app.initialize = AsyncMock()
                mock_app.start = AsyncMock()
                mock_app.shutdown = AsyncMock()
                mock_app_class.builder.return_value.token.return_value.build.return_value = mock_app
                
                await bootstrapper.start_application()
                
                yield bootstrapper
                
                await bootstrapper.shutdown_application()

    def create_load_test_update(self, message_id: int, text: str = "Load test message", 
                               user_id: int = None, chat_id: int = None) -> Update:
        """Create an update for load testing."""
        if user_id is None:
            user_id = 10000 + (message_id % 1000)  # Vary user IDs
        if chat_id is None:
            chat_id = 20000 + (message_id % 100)   # Vary chat IDs

        user = Mock(spec=User)
        user.id = user_id
        user.first_name = f"LoadTestUser{user_id}"
        user.username = f"loaduser{user_id}"
        user.is_bot = False

        chat = Mock(spec=Chat)
        chat.id = chat_id
        chat.type = "private" if message_id % 3 == 0 else "group"

        message = Mock(spec=Message)
        message.message_id = message_id
        message.text = f"{text} #{message_id}"
        message.from_user = user
        message.chat = chat
        message.date = Mock()

        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat

        return update

    def create_voice_load_test_update(self, message_id: int, user_id: int = None) -> Update:
        """Create a voice update for load testing."""
        if user_id is None:
            user_id = 10000 + (message_id % 1000)

        user = Mock(spec=User)
        user.id = user_id
        user.first_name = f"VoiceUser{user_id}"

        chat = Mock(spec=Chat)
        chat.id = 20000 + (message_id % 100)
        chat.type = "private"

        voice = Mock(spec=Voice)
        voice.file_id = f"voice_load_test_{message_id}"
        voice.duration = 5 + (message_id % 10)  # Vary duration

        message = Mock(spec=Message)
        message.voice = voice
        message.from_user = user
        message.chat = chat
        message.text = None

        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat

        return update

    def create_callback_load_test_update(self, callback_id: int) -> Update:
        """Create a callback query for load testing."""
        user = Mock(spec=User)
        user.id = 10000 + (callback_id % 1000)
        user.first_name = f"CallbackUser{user.id}"

        callback_query = Mock(spec=CallbackQuery)
        callback_query.data = f"load_test_callback_{callback_id}"
        callback_query.from_user = user
        callback_query.answer = AsyncMock()

        update = Mock(spec=Update)
        update.callback_query = callback_query
        update.effective_user = user

        return update

    @pytest.mark.asyncio
    async def test_high_volume_message_processing(self, load_test_application):
        """Test processing high volume of messages."""
        message_service = load_test_application.service_registry.get_service('message_handler_service')
        if not message_service:
            pytest.skip("MessageHandlerService not available")

        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()

        with patch('modules.message_handler_service.gpt_response') as mock_gpt_response, \
             patch('modules.message_handler_service.update_message_history') as mock_update_history:
            
            mock_gpt_response.return_value = None

            # Test with 500 messages
            message_count = 500
            batch_size = 50
            
            total_start_time = time.time()
            
            for batch_start in range(0, message_count, batch_size):
                batch_end = min(batch_start + batch_size, message_count)
                batch_tasks = []
                
                batch_start_time = time.time()
                
                for i in range(batch_start, batch_end):
                    update = self.create_load_test_update(i, "High volume test message")
                    task = message_service.handle_text_message(update, context)
                    batch_tasks.append(task)
                
                # Process batch
                results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                batch_time = time.time() - batch_start_time
                batch_throughput = len(batch_tasks) / batch_time
                
                # Each batch should maintain good throughput
                assert batch_throughput > 20, f"Batch throughput too low: {batch_throughput:.2f} msg/sec"
                
                # Most messages should process successfully
                successful = sum(1 for r in results if not isinstance(r, Exception))
                success_rate = successful / len(batch_tasks)
                assert success_rate > 0.9, f"Batch success rate too low: {success_rate:.2%}"
            
            total_time = time.time() - total_start_time
            overall_throughput = message_count / total_time
            
            print(f"High volume test: {message_count} messages in {total_time:.2f}s ({overall_throughput:.2f} msg/sec)")
            
            # Overall throughput should be maintained
            assert overall_throughput > 15, f"Overall throughput too low: {overall_throughput:.2f} msg/sec"

    @pytest.mark.asyncio
    async def test_concurrent_user_simulation(self, load_test_application):
        """Test concurrent users sending messages simultaneously."""
        message_service = load_test_application.service_registry.get_service('message_handler_service')
        if not message_service:
            pytest.skip("MessageHandlerService not available")

        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()

        with patch('modules.message_handler_service.gpt_response') as mock_gpt_response:
            mock_gpt_response.return_value = None

            # Simulate 100 concurrent users, each sending 5 messages
            user_count = 100
            messages_per_user = 5
            
            start_time = time.time()
            
            # Create tasks for all users
            all_tasks = []
            for user_id in range(user_count):
                for msg_num in range(messages_per_user):
                    message_id = user_id * messages_per_user + msg_num
                    update = self.create_load_test_update(
                        message_id, 
                        f"Concurrent user {user_id} message {msg_num}",
                        user_id=10000 + user_id,
                        chat_id=20000 + user_id
                    )
                    task = message_service.handle_text_message(update, context)
                    all_tasks.append(task)
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*all_tasks, return_exceptions=True)
            
            total_time = time.time() - start_time
            total_messages = user_count * messages_per_user
            throughput = total_messages / total_time
            
            # Check success rate
            successful = sum(1 for r in results if not isinstance(r, Exception))
            success_rate = successful / len(results)
            
            print(f"Concurrent users: {user_count} users, {total_messages} messages in {total_time:.2f}s ({throughput:.2f} msg/sec)")
            print(f"Success rate: {success_rate:.2%}")
            
            # Should handle concurrent load well
            assert throughput > 30, f"Concurrent throughput too low: {throughput:.2f} msg/sec"
            assert success_rate > 0.85, f"Success rate too low: {success_rate:.2%}"

    @pytest.mark.asyncio
    async def test_mixed_message_type_load(self, load_test_application):
        """Test load with mixed message types (text, voice, callbacks)."""
        message_service = load_test_application.service_registry.get_service('message_handler_service')
        speech_service = load_test_application.service_registry.get_service('speech_recognition_service')
        callback_service = load_test_application.service_registry.get_service('callback_handler_service')
        
        if not message_service:
            pytest.skip("MessageHandlerService not available")

        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()

        with patch('modules.message_handler_service.gpt_response') as mock_gpt_response:
            mock_gpt_response.return_value = None

            # Create mixed load: 60% text, 25% voice, 15% callbacks
            total_operations = 300
            text_count = int(total_operations * 0.6)
            voice_count = int(total_operations * 0.25)
            callback_count = total_operations - text_count - voice_count

            start_time = time.time()
            all_tasks = []

            # Text messages
            for i in range(text_count):
                update = self.create_load_test_update(i, "Mixed load text message")
                task = message_service.handle_text_message(update, context)
                all_tasks.append(('text', task))

            # Voice messages (if speech service available)
            if speech_service:
                with patch.object(speech_service, '_download_voice_file') as mock_download, \
                     patch.object(speech_service, '_transcribe_audio') as mock_transcribe:
                    
                    mock_download.return_value = b"fake_audio_data"
                    mock_transcribe.return_value = "Transcribed text"

                    for i in range(voice_count):
                        update = self.create_voice_load_test_update(i)
                        task = speech_service.handle_voice_message(update, context)
                        all_tasks.append(('voice', task))

            # Callback queries (if callback service available)
            if callback_service:
                for i in range(callback_count):
                    update = self.create_callback_load_test_update(i)
                    task = callback_service.handle_callback_query(update, context)
                    all_tasks.append(('callback', task))

            # Execute all mixed tasks
            tasks_only = [task for _, task in all_tasks]
            results = await asyncio.gather(*tasks_only, return_exceptions=True)

            total_time = time.time() - start_time
            throughput = len(all_tasks) / total_time

            # Analyze results by type
            successful = sum(1 for r in results if not isinstance(r, Exception))
            success_rate = successful / len(results)

            print(f"Mixed load: {len(all_tasks)} operations in {total_time:.2f}s ({throughput:.2f} ops/sec)")
            print(f"Text: {text_count}, Voice: {voice_count}, Callbacks: {callback_count}")
            print(f"Success rate: {success_rate:.2%}")

            # Should handle mixed load efficiently
            assert throughput > 25, f"Mixed load throughput too low: {throughput:.2f} ops/sec"
            assert success_rate > 0.8, f"Mixed load success rate too low: {success_rate:.2%}"

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, load_test_application):
        """Test memory usage during sustained load."""
        message_service = load_test_application.service_registry.get_service('message_handler_service')
        if not message_service:
            pytest.skip("MessageHandlerService not available")

        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        with patch('modules.message_handler_service.gpt_response') as mock_gpt_response:
            mock_gpt_response.return_value = None

            # Process messages in waves to test memory stability
            wave_count = 10
            messages_per_wave = 50
            memory_readings = []

            for wave in range(wave_count):
                wave_tasks = []
                
                for i in range(messages_per_wave):
                    message_id = wave * messages_per_wave + i
                    update = self.create_load_test_update(message_id, f"Memory test wave {wave}")
                    task = message_service.handle_text_message(update, context)
                    wave_tasks.append(task)

                # Process wave
                await asyncio.gather(*wave_tasks, return_exceptions=True)

                # Check memory usage
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_readings.append(current_memory)
                
                # Allow some time for garbage collection
                await asyncio.sleep(0.1)

            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            max_memory = max(memory_readings)
            memory_increase = final_memory - initial_memory
            peak_increase = max_memory - initial_memory

            print(f"Memory usage: {initial_memory:.2f}MB -> {final_memory:.2f}MB (peak: {max_memory:.2f}MB)")
            print(f"Total increase: {memory_increase:.2f}MB, Peak increase: {peak_increase:.2f}MB")

            # Memory usage should be reasonable
            assert memory_increase < 200, f"Memory increase too high: {memory_increase:.2f}MB"
            assert peak_increase < 300, f"Peak memory increase too high: {peak_increase:.2f}MB"

    @pytest.mark.asyncio
    async def test_sustained_load_performance(self, load_test_application):
        """Test performance under sustained load over time."""
        message_service = load_test_application.service_registry.get_service('message_handler_service')
        if not message_service:
            pytest.skip("MessageHandlerService not available")

        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()

        with patch('modules.message_handler_service.gpt_response') as mock_gpt_response:
            mock_gpt_response.return_value = None

            # Run sustained load for multiple intervals
            interval_count = 5
            messages_per_interval = 100
            interval_duration = 2.0  # seconds
            
            throughput_readings = []

            for interval in range(interval_count):
                interval_start = time.time()
                interval_tasks = []

                # Create messages for this interval
                for i in range(messages_per_interval):
                    message_id = interval * messages_per_interval + i
                    update = self.create_load_test_update(message_id, f"Sustained load interval {interval}")
                    task = message_service.handle_text_message(update, context)
                    interval_tasks.append(task)

                # Process interval messages
                results = await asyncio.gather(*interval_tasks, return_exceptions=True)
                
                interval_time = time.time() - interval_start
                interval_throughput = messages_per_interval / interval_time
                throughput_readings.append(interval_throughput)

                successful = sum(1 for r in results if not isinstance(r, Exception))
                success_rate = successful / len(results)

                print(f"Interval {interval + 1}: {interval_throughput:.2f} msg/sec, {success_rate:.2%} success")

                # Each interval should maintain good performance
                assert interval_throughput > 20, f"Interval {interval} throughput too low: {interval_throughput:.2f}"
                assert success_rate > 0.9, f"Interval {interval} success rate too low: {success_rate:.2%}"

                # Brief pause between intervals
                await asyncio.sleep(0.5)

            # Check performance consistency
            avg_throughput = sum(throughput_readings) / len(throughput_readings)
            min_throughput = min(throughput_readings)
            max_throughput = max(throughput_readings)
            
            print(f"Sustained load summary: avg={avg_throughput:.2f}, min={min_throughput:.2f}, max={max_throughput:.2f} msg/sec")

            # Performance should be consistent
            assert avg_throughput > 25, f"Average throughput too low: {avg_throughput:.2f} msg/sec"
            assert min_throughput > 15, f"Minimum throughput too low: {min_throughput:.2f} msg/sec"
            
            # Performance shouldn't degrade significantly over time
            performance_variance = (max_throughput - min_throughput) / avg_throughput
            assert performance_variance < 0.5, f"Performance variance too high: {performance_variance:.2%}"

    @pytest.mark.asyncio
    async def test_error_handling_under_load(self, load_test_application):
        """Test error handling performance under load conditions."""
        message_service = load_test_application.service_registry.get_service('message_handler_service')
        if not message_service:
            pytest.skip("MessageHandlerService not available")

        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()

        with patch('modules.message_handler_service.gpt_response') as mock_gpt_response:
            # Make 30% of requests fail
            call_count = 0
            def gpt_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count % 3 == 0:  # Every 3rd call fails
                    raise Exception("Simulated GPT error")
                return None
            
            mock_gpt_response.side_effect = gpt_side_effect

            # Process messages with errors
            message_count = 200
            start_time = time.time()

            tasks = []
            for i in range(message_count):
                update = self.create_load_test_update(i, "Error handling load test")
                task = message_service.handle_text_message(update, context)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            total_time = time.time() - start_time
            throughput = message_count / total_time

            # Count successful vs failed operations
            successful = sum(1 for r in results if not isinstance(r, Exception))
            success_rate = successful / len(results)

            print(f"Error handling load: {message_count} messages in {total_time:.2f}s ({throughput:.2f} msg/sec)")
            print(f"Success rate with 30% error injection: {success_rate:.2%}")

            # Should maintain reasonable throughput even with errors
            assert throughput > 15, f"Error handling throughput too low: {throughput:.2f} msg/sec"
            
            # Should handle errors gracefully (not crash)
            assert len(results) == message_count, "Not all messages were processed"

    @pytest.mark.asyncio
    async def test_service_initialization_performance_under_load(self):
        """Test service initialization performance when creating multiple instances."""
        initialization_times = []
        
        # Test creating multiple application instances
        for i in range(5):
            with patch.dict('os.environ', {
                'TELEGRAM_BOT_TOKEN': f'perf_test_token_{i}',
                'ERROR_CHANNEL_ID': '-1001234567890'
            }):
                bootstrapper = ApplicationBootstrapper()
                
                start_time = time.time()
                service_registry = await bootstrapper.configure_services()
                init_time = time.time() - start_time
                
                initialization_times.append(init_time)
                
                # Verify services are properly initialized
                assert service_registry.get_service('config_manager') is not None
                assert service_registry.get_service('database') is not None

        avg_init_time = sum(initialization_times) / len(initialization_times)
        max_init_time = max(initialization_times)
        
        print(f"Service initialization: avg={avg_init_time:.3f}s, max={max_init_time:.3f}s")
        
        # Initialization should be consistently fast
        assert avg_init_time < 2.0, f"Average initialization too slow: {avg_init_time:.3f}s"
        assert max_init_time < 3.0, f"Maximum initialization too slow: {max_init_time:.3f}s"

    @pytest.mark.asyncio
    async def test_callback_processing_load(self, load_test_application):
        """Test callback processing under load."""
        callback_service = load_test_application.service_registry.get_service('callback_handler_service')
        if not callback_service:
            pytest.skip("CallbackHandlerService not available")

        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()

        # Test processing many callbacks
        callback_count = 300
        start_time = time.time()

        tasks = []
        for i in range(callback_count):
            update = self.create_callback_load_test_update(i)
            task = callback_service.handle_callback_query(update, context)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time
        throughput = callback_count / total_time

        successful = sum(1 for r in results if not isinstance(r, Exception))
        success_rate = successful / len(results)

        print(f"Callback load: {callback_count} callbacks in {total_time:.2f}s ({throughput:.2f} callbacks/sec)")
        print(f"Success rate: {success_rate:.2%}")

        # Should handle callback load efficiently
        assert throughput > 50, f"Callback throughput too low: {throughput:.2f} callbacks/sec"
        assert success_rate > 0.9, f"Callback success rate too low: {success_rate:.2%}"

    @pytest.mark.asyncio
    async def test_startup_shutdown_performance_under_load(self):
        """Test startup and shutdown performance under load conditions."""
        startup_times = []
        shutdown_times = []
        
        # Test multiple startup/shutdown cycles
        for cycle in range(3):
            with patch.dict('os.environ', {
                'TELEGRAM_BOT_TOKEN': f'cycle_test_token_{cycle}',
                'ERROR_CHANNEL_ID': '-1001234567890'
            }):
                bootstrapper = ApplicationBootstrapper()
                
                with patch('modules.bot_application.Application') as mock_app_class:
                    mock_app = Mock()
                    mock_app.initialize = AsyncMock()
                    mock_app.start = AsyncMock()
                    mock_app.shutdown = AsyncMock()
                    mock_app_class.builder.return_value.token.return_value.build.return_value = mock_app
                    
                    # Measure startup time
                    startup_start = time.time()
                    await bootstrapper.start_application()
                    startup_time = time.time() - startup_start
                    startup_times.append(startup_time)
                    
                    # Measure shutdown time
                    shutdown_start = time.time()
                    await bootstrapper.shutdown_application()
                    shutdown_time = time.time() - shutdown_start
                    shutdown_times.append(shutdown_time)

        avg_startup = sum(startup_times) / len(startup_times)
        avg_shutdown = sum(shutdown_times) / len(shutdown_times)
        max_startup = max(startup_times)
        max_shutdown = max(shutdown_times)

        print(f"Startup performance: avg={avg_startup:.3f}s, max={max_startup:.3f}s")
        print(f"Shutdown performance: avg={avg_shutdown:.3f}s, max={max_shutdown:.3f}s")

        # Should maintain good startup/shutdown performance
        assert avg_startup < 5.0, f"Average startup too slow: {avg_startup:.3f}s"
        assert avg_shutdown < 3.0, f"Average shutdown too slow: {avg_shutdown:.3f}s"
        assert max_startup < 8.0, f"Maximum startup too slow: {max_startup:.3f}s"
        assert max_shutdown < 5.0, f"Maximum shutdown too slow: {max_shutdown:.3f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])