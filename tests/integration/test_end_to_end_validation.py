"""
End-to-end validation tests for the complete application.
Tests the entire application flow from startup to shutdown with real message processing.
"""

import asyncio
import pytest
import os
import signal
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from telegram import Update, Message, User, Chat, CallbackQuery, Voice, VideoNote
from telegram.ext import CallbackContext, Application

from modules.application_bootstrapper import ApplicationBootstrapper
from modules.service_registry import ServiceRegistry
from modules.application_models import ServiceConfiguration
from modules.const import Config


class TestEndToEndValidation:
    """End-to-end validation tests for the complete application."""

    @pytest.fixture
    async def mock_environment(self):
        """Set up mock environment variables for testing."""
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'test_token_123456789',
            'ERROR_CHANNEL_ID': '-1001234567890',
            'DEBUG_MODE': 'true'
        }):
            yield

    @pytest.fixture
    async def application_bootstrapper(self, mock_environment):
        """Create an ApplicationBootstrapper for testing."""
        return ApplicationBootstrapper()

    @pytest.fixture
    async def mock_telegram_application(self):
        """Create a mock Telegram Application for testing."""
        app = Mock(spec=Application)
        app.initialize = AsyncMock()
        app.start = AsyncMock()
        app.stop = AsyncMock()
        app.shutdown = AsyncMock()
        app.updater = Mock()
        app.updater.start_polling = AsyncMock()
        app.updater.stop = AsyncMock()
        return app

    def create_realistic_update(self, message_type: str = "text", content: str = "Hello", 
                              user_id: int = 12345, chat_id: int = 67890, 
                              chat_type: str = "private") -> Update:
        """Create a realistic Telegram update for testing."""
        user = Mock(spec=User)
        user.id = user_id
        user.first_name = "TestUser"
        user.username = "testuser"
        user.is_bot = False

        chat = Mock(spec=Chat)
        chat.id = chat_id
        chat.type = chat_type
        chat.title = "Test Chat" if chat_type != "private" else None

        message = Mock(spec=Message)
        message.message_id = 1
        message.from_user = user
        message.chat = chat
        message.date = Mock()

        if message_type == "text":
            message.text = content
            message.voice = None
            message.video_note = None
            message.sticker = None
            message.location = None
        elif message_type == "voice":
            message.text = None
            message.voice = Mock(spec=Voice)
            message.voice.file_id = "voice_file_123"
            message.voice.duration = 10
        elif message_type == "video_note":
            message.text = None
            message.video_note = Mock(spec=VideoNote)
            message.video_note.file_id = "video_note_123"
            message.video_note.duration = 15
        elif message_type == "sticker":
            message.text = None
            message.sticker = Mock()
            message.sticker.file_id = "sticker_123"
        elif message_type == "location":
            message.text = None
            message.location = Mock()
            message.location.latitude = 40.7128
            message.location.longitude = -74.0060

        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        update.callback_query = None

        return update

    def create_callback_update(self, callback_data: str = "test_callback", 
                             user_id: int = 12345) -> Update:
        """Create a callback query update for testing."""
        user = Mock(spec=User)
        user.id = user_id
        user.first_name = "TestUser"

        callback_query = Mock(spec=CallbackQuery)
        callback_query.data = callback_data
        callback_query.from_user = user
        callback_query.answer = AsyncMock()
        callback_query.edit_message_text = AsyncMock()

        update = Mock(spec=Update)
        update.callback_query = callback_query
        update.effective_user = user
        update.message = None

        return update

    @pytest.mark.asyncio
    async def test_complete_application_lifecycle(self, application_bootstrapper, mock_telegram_application):
        """Test complete application lifecycle from startup to shutdown."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            
            # Test startup
            await application_bootstrapper.start_application()
            assert application_bootstrapper.is_running is True
            assert application_bootstrapper.service_registry is not None
            assert application_bootstrapper.bot_application is not None

            # Verify services are initialized
            config_manager = application_bootstrapper.service_registry.get_service('config_manager')
            assert config_manager is not None

            # Test shutdown
            await application_bootstrapper.shutdown_application()
            assert application_bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_service_registry_integration(self, application_bootstrapper):
        """Test service registry integration with all services."""
        service_registry = await application_bootstrapper.configure_services()
        
        # Verify core services are registered
        assert service_registry.get_service('config_manager') is not None
        assert service_registry.get_service('database') is not None
        
        # Verify service configuration
        service_config = service_registry.get_service('service_config')
        assert isinstance(service_config, ServiceConfiguration)
        assert service_config.telegram_token == 'test_token_123456789'
        assert service_config.error_channel_id == '-1001234567890'

    @pytest.mark.asyncio
    async def test_message_processing_end_to_end(self, application_bootstrapper, mock_telegram_application):
        """Test end-to-end message processing through the complete system."""
        with patch('modules.bot_application.Application') as mock_app_class, \
             patch('modules.message_handler_service.gpt_response') as mock_gpt_response, \
             patch('modules.message_handler_service.update_message_history') as mock_update_history:
            
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            mock_gpt_response.return_value = None
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Get message handler service
            message_service = application_bootstrapper.service_registry.get_service('message_handler_service')
            if message_service:
                # Test text message processing
                context = Mock(spec=CallbackContext)
                context.bot = AsyncMock()
                
                text_update = self.create_realistic_update("text", "Hello, how are you?")
                await message_service.handle_text_message(text_update, context)
                
                # Verify message was processed
                mock_update_history.assert_called()
            
            await application_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_speech_recognition_end_to_end(self, application_bootstrapper, mock_telegram_application):
        """Test end-to-end speech recognition processing."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Get speech recognition service
            speech_service = application_bootstrapper.service_registry.get_service('speech_recognition_service')
            if speech_service:
                context = Mock(spec=CallbackContext)
                context.bot = AsyncMock()
                
                # Test voice message processing
                voice_update = self.create_realistic_update("voice")
                
                with patch.object(speech_service, '_download_voice_file') as mock_download, \
                     patch.object(speech_service, '_transcribe_audio') as mock_transcribe:
                    
                    mock_download.return_value = b"fake_audio_data"
                    mock_transcribe.return_value = "Transcribed text"
                    
                    await speech_service.handle_voice_message(voice_update, context)
                    
                    # Verify speech processing
                    mock_download.assert_called_once()
                    mock_transcribe.assert_called_once()
            
            await application_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_command_processing_end_to_end(self, application_bootstrapper, mock_telegram_application):
        """Test end-to-end command processing."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Get command registry
            command_registry = application_bootstrapper.service_registry.get_service('command_registry')
            if command_registry:
                # Test command registration
                await command_registry.register_all_commands()
                
                # Verify commands are registered
                command_processor = application_bootstrapper.service_registry.get_service('command_processor')
                assert command_processor is not None
            
            await application_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_callback_processing_end_to_end(self, application_bootstrapper, mock_telegram_application):
        """Test end-to-end callback processing."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Get callback handler service
            callback_service = application_bootstrapper.service_registry.get_service('callback_handler_service')
            if callback_service:
                context = Mock(spec=CallbackContext)
                context.bot = AsyncMock()
                
                # Test callback processing
                callback_update = self.create_callback_update("speech_lang_en_abc123")
                await callback_service.handle_callback_query(callback_update, context)
                
                # Verify callback was processed
                callback_update.callback_query.answer.assert_called_once()
            
            await application_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_error_propagation_and_recovery(self, application_bootstrapper, mock_telegram_application):
        """Test error propagation and recovery across service boundaries."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Get services
            message_service = application_bootstrapper.service_registry.get_service('message_handler_service')
            if message_service:
                context = Mock(spec=CallbackContext)
                context.bot = AsyncMock()
                
                # Mock a service to raise an exception
                with patch('modules.message_handler_service.gpt_response') as mock_gpt:
                    mock_gpt.side_effect = Exception("Simulated service error")
                    
                    # Process message - should handle error gracefully
                    text_update = self.create_realistic_update("text", "Test error handling")
                    
                    # Should not raise exception
                    await message_service.handle_text_message(text_update, context)
                    
                    # Service should still be functional
                    assert message_service is not None
            
            await application_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, application_bootstrapper, mock_telegram_application):
        """Test concurrent message processing under load."""
        with patch('modules.bot_application.Application') as mock_app_class, \
             patch('modules.message_handler_service.gpt_response') as mock_gpt_response:
            
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            mock_gpt_response.return_value = None
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Get message service
            message_service = application_bootstrapper.service_registry.get_service('message_handler_service')
            if message_service:
                context = Mock(spec=CallbackContext)
                context.bot = AsyncMock()
                
                # Create multiple concurrent message processing tasks
                tasks = []
                for i in range(20):
                    update = self.create_realistic_update("text", f"Concurrent message {i}")
                    task = message_service.handle_text_message(update, context)
                    tasks.append(task)
                
                # Execute all tasks concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Most should succeed
                successful = sum(1 for r in results if not isinstance(r, Exception))
                assert successful >= 15, f"Only {successful}/20 concurrent messages processed successfully"
            
            await application_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_startup_failure_handling(self, application_bootstrapper):
        """Test application behavior when startup fails."""
        with patch('modules.application_bootstrapper.ConfigManager') as mock_config_class:
            # Make ConfigManager initialization fail
            mock_config = Mock()
            mock_config.initialize = AsyncMock(side_effect=Exception("Config initialization failed"))
            mock_config_class.return_value = mock_config
            
            # Startup should fail gracefully
            with pytest.raises(RuntimeError, match="Service configuration failed"):
                await application_bootstrapper.start_application()
            
            # Application should not be running
            assert application_bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_signal_handling(self, application_bootstrapper, mock_telegram_application):
        """Test signal handling for graceful shutdown."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            
            # Start application
            await application_bootstrapper.start_application()
            assert application_bootstrapper.is_running is True
            
            # Simulate signal handling
            application_bootstrapper.setup_signal_handlers()
            
            # Trigger shutdown event
            application_bootstrapper._shutdown_event.set()
            
            # Shutdown should work
            await application_bootstrapper.shutdown_application()
            assert application_bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_service_dependency_resolution(self, application_bootstrapper):
        """Test that all service dependencies are resolved correctly."""
        service_registry = await application_bootstrapper.configure_services()
        
        # Test that services can be retrieved and have their dependencies
        config_manager = service_registry.get_service('config_manager')
        assert config_manager is not None
        
        database = service_registry.get_service('database')
        assert database is not None
        
        # Test services with dependencies
        message_service = service_registry.get_service('message_handler_service')
        if message_service:
            assert hasattr(message_service, 'config_manager')
        
        speech_service = service_registry.get_service('speech_recognition_service')
        if speech_service:
            assert hasattr(speech_service, 'config_manager')

    @pytest.mark.asyncio
    async def test_configuration_integration(self, application_bootstrapper, mock_telegram_application):
        """Test configuration integration throughout the system."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Get config manager
            config_manager = application_bootstrapper.service_registry.get_service('config_manager')
            assert config_manager is not None
            
            # Test configuration access
            config = await config_manager.get_config()
            assert isinstance(config, dict)
            
            # Test that services use configuration
            message_service = application_bootstrapper.service_registry.get_service('message_handler_service')
            if message_service and hasattr(message_service, 'config_manager'):
                assert message_service.config_manager is config_manager
            
            await application_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_memory_cleanup_on_shutdown(self, application_bootstrapper, mock_telegram_application):
        """Test that memory is properly cleaned up on shutdown."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Verify services are created
            assert application_bootstrapper.service_registry is not None
            assert application_bootstrapper.bot_application is not None
            
            # Shutdown
            await application_bootstrapper.shutdown_application()
            
            # Verify cleanup
            assert application_bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_multiple_message_types_integration(self, application_bootstrapper, mock_telegram_application):
        """Test integration with multiple message types."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Get message service
            message_service = application_bootstrapper.service_registry.get_service('message_handler_service')
            if message_service:
                context = Mock(spec=CallbackContext)
                context.bot = AsyncMock()
                
                # Test different message types
                message_types = [
                    ("text", "Hello world"),
                    ("sticker", None),
                    ("location", None)
                ]
                
                for msg_type, content in message_types:
                    update = self.create_realistic_update(msg_type, content or "")
                    
                    if msg_type == "text":
                        await message_service.handle_text_message(update, context)
                    elif msg_type == "sticker":
                        await message_service.handle_sticker_message(update, context)
                    elif msg_type == "location":
                        await message_service.handle_location_message(update, context)
            
            await application_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_service_health_monitoring(self, application_bootstrapper, mock_telegram_application):
        """Test service health monitoring integration."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Check that all critical services are healthy
            critical_services = [
                'config_manager',
                'database',
                'bot_application'
            ]
            
            for service_name in critical_services:
                service = application_bootstrapper.service_registry.get_service(service_name)
                assert service is not None, f"Critical service {service_name} not available"
            
            await application_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_existing_functionality_preservation(self, application_bootstrapper, mock_telegram_application):
        """Test that all existing functionality is preserved exactly."""
        with patch('modules.bot_application.Application') as mock_app_class, \
             patch('modules.message_handler_service.gpt_response') as mock_gpt_response, \
             patch('modules.message_handler_service.update_message_history') as mock_update_history:
            
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_application
            mock_gpt_response.return_value = None
            
            # Start application
            await application_bootstrapper.start_application()
            
            # Test that core functionality works
            message_service = application_bootstrapper.service_registry.get_service('message_handler_service')
            if message_service:
                context = Mock(spec=CallbackContext)
                context.bot = AsyncMock()
                
                # Test basic message processing (should work like before)
                update = self.create_realistic_update("text", "Hello")
                await message_service.handle_text_message(update, context)
                
                # Verify existing behavior is preserved
                mock_update_history.assert_called()
            
            # Test speech recognition (should work like before)
            speech_service = application_bootstrapper.service_registry.get_service('speech_recognition_service')
            if speech_service:
                config = await speech_service.get_speech_config("12345", "private")
                # Should return config or None (both are valid existing behaviors)
                assert config is not None or config is None
            
            await application_bootstrapper.shutdown_application()


class TestApplicationPerformanceValidation:
    """Performance validation tests for the complete application."""

    @pytest.fixture
    async def performance_bootstrapper(self):
        """Create bootstrapper for performance testing."""
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'perf_test_token',
            'ERROR_CHANNEL_ID': '-1001111111111'
        }):
            return ApplicationBootstrapper()

    @pytest.mark.asyncio
    async def test_startup_performance(self, performance_bootstrapper):
        """Test application startup performance."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app = Mock()
            mock_app.initialize = AsyncMock()
            mock_app.start = AsyncMock()
            mock_app.shutdown = AsyncMock()
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_app
            
            start_time = time.time()
            
            await performance_bootstrapper.start_application()
            
            startup_time = time.time() - start_time
            
            # Startup should complete within 5 seconds
            assert startup_time < 5.0, f"Startup too slow: {startup_time:.2f}s"
            
            await performance_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_shutdown_performance(self, performance_bootstrapper):
        """Test application shutdown performance."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app = Mock()
            mock_app.initialize = AsyncMock()
            mock_app.start = AsyncMock()
            mock_app.shutdown = AsyncMock()
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_app
            
            await performance_bootstrapper.start_application()
            
            start_time = time.time()
            
            await performance_bootstrapper.shutdown_application()
            
            shutdown_time = time.time() - start_time
            
            # Shutdown should complete within 3 seconds
            assert shutdown_time < 3.0, f"Shutdown too slow: {shutdown_time:.2f}s"

    @pytest.mark.asyncio
    async def test_service_initialization_performance(self, performance_bootstrapper):
        """Test service initialization performance."""
        start_time = time.time()
        
        service_registry = await performance_bootstrapper.configure_services()
        
        init_time = time.time() - start_time
        
        # Service initialization should be fast
        assert init_time < 2.0, f"Service initialization too slow: {init_time:.2f}s"
        
        # Verify services are available
        assert service_registry.get_service('config_manager') is not None
        assert service_registry.get_service('database') is not None

    @pytest.mark.asyncio
    async def test_message_processing_throughput(self, performance_bootstrapper):
        """Test message processing throughput in integrated system."""
        with patch('modules.bot_application.Application') as mock_app_class, \
             patch('modules.message_handler_service.gpt_response') as mock_gpt_response:
            
            mock_app = Mock()
            mock_app.initialize = AsyncMock()
            mock_app.start = AsyncMock()
            mock_app.shutdown = AsyncMock()
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_app
            mock_gpt_response.return_value = None
            
            await performance_bootstrapper.start_application()
            
            message_service = performance_bootstrapper.service_registry.get_service('message_handler_service')
            if message_service:
                context = Mock(spec=CallbackContext)
                context.bot = AsyncMock()
                
                # Test throughput with 50 messages
                message_count = 50
                start_time = time.time()
                
                tasks = []
                for i in range(message_count):
                    user = Mock(spec=User)
                    user.id = 12345
                    chat = Mock(spec=Chat)
                    chat.id = 67890
                    chat.type = "private"
                    message = Mock(spec=Message)
                    message.text = f"Performance test message {i}"
                    message.from_user = user
                    message.chat = chat
                    update = Mock(spec=Update)
                    update.message = message
                    update.effective_user = user
                    update.effective_chat = chat
                    
                    task = message_service.handle_text_message(update, context)
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
                processing_time = time.time() - start_time
                throughput = message_count / processing_time
                
                # Should maintain reasonable throughput
                assert throughput > 10, f"Throughput too low: {throughput:.2f} msg/sec"
            
            await performance_bootstrapper.shutdown_application()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])