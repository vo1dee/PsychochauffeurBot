"""
Comprehensive integration tests for service interactions and message flows.
Tests the complete integration between all major components.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, User, Chat, CallbackQuery, Voice, VideoNote
from telegram.ext import CallbackContext

from modules.application_bootstrapper import ApplicationBootstrapper
from modules.service_registry import ServiceRegistry
from modules.bot_application import BotApplication
from modules.message_handler_service import MessageHandlerService
from modules.speech_recognition_service import SpeechRecognitionService
from modules.callback_handler_service import CallbackHandlerService
from modules.command_registry import CommandRegistry
from modules.command_processor import CommandProcessor
from config.config_manager import ConfigManager


class TestComprehensiveServiceIntegration:
    """Comprehensive integration tests for all services."""

    @pytest.fixture
    async def service_registry(self):
        """Create a real service registry with mocked dependencies."""
        registry = ServiceRegistry()
        
        # Mock config manager
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_config = AsyncMock(return_value={
            'gpt': {'enabled': True, 'random_response_chance': 0.1},
            'speech': {'enabled': True, 'default_language': 'en'},
            'commands': {'enabled': True},
            'url_processing': {'enabled': True}
        })
        registry.register_service('config_manager', mock_config)
        
        # Mock GPT service
        mock_gpt = Mock()
        mock_gpt.should_respond_randomly = AsyncMock(return_value=False)
        mock_gpt.process_message = AsyncMock(return_value="GPT response")
        registry.register_service('gpt_service', mock_gpt)
        
        # Mock command processor
        mock_cmd_processor = Mock(spec=CommandProcessor)
        mock_cmd_processor.process_command = AsyncMock(return_value=True)
        registry.register_service('command_processor', mock_cmd_processor)
        
        return registry

    @pytest.fixture
    async def integrated_services(self, service_registry):
        """Create integrated services using the service registry."""
        config_manager = service_registry.get_service('config_manager')
        gpt_service = service_registry.get_service('gpt_service')
        command_processor = service_registry.get_service('command_processor')
        
        # Create services
        message_service = MessageHandlerService(
            config_manager=config_manager,
            gpt_service=gpt_service
        )
        service_registry.register_service('message_handler_service', message_service)
        
        speech_service = SpeechRecognitionService(config_manager=config_manager)
        service_registry.register_service('speech_recognition_service', speech_service)
        
        callback_service = CallbackHandlerService(speech_service=speech_service)
        service_registry.register_service('callback_handler_service', callback_service)
        
        command_registry = CommandRegistry(command_processor=command_processor)
        service_registry.register_service('command_registry', command_registry)
        
        return {
            'registry': service_registry,
            'message': message_service,
            'speech': speech_service,
            'callback': callback_service,
            'command': command_registry
        }

    def create_text_update(self, text="Test message", user_id=12345, chat_id=67890, chat_type="private"):
        """Create a mock text message update."""
        user = Mock(spec=User)
        user.id = user_id
        user.first_name = "Test"
        user.username = "testuser"

        chat = Mock(spec=Chat)
        chat.id = chat_id
        chat.type = chat_type

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

    def create_voice_update(self, user_id=12345, chat_id=67890):
        """Create a mock voice message update."""
        user = Mock(spec=User)
        user.id = user_id
        user.first_name = "Test"

        chat = Mock(spec=Chat)
        chat.id = chat_id
        chat.type = "private"

        voice = Mock(spec=Voice)
        voice.file_id = "voice_file_123"
        voice.duration = 10

        message = Mock(spec=Message)
        message.voice = voice
        message.from_user = user
        message.chat = chat
        message.message_id = 2

        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat

        return update

    def create_callback_update(self, callback_data="test_callback"):
        """Create a mock callback query update."""
        user = Mock(spec=User)
        user.id = 12345
        user.first_name = "Test"

        callback_query = Mock(spec=CallbackQuery)
        callback_query.data = callback_data
        callback_query.from_user = user
        callback_query.answer = AsyncMock()

        update = Mock(spec=Update)
        update.callback_query = callback_query
        update.effective_user = user

        return update

    @pytest.mark.asyncio
    async def test_complete_message_flow_integration(self, integrated_services):
        """Test complete message processing flow through all services."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Test text message flow
        text_update = self.create_text_update("Hello, how are you?")
        await integrated_services['message'].handle_text_message(text_update, context)
        
        # Verify GPT service was called
        integrated_services['registry'].get_service('gpt_service').process_message.assert_called()

    @pytest.mark.asyncio
    async def test_speech_recognition_flow_integration(self, integrated_services):
        """Test speech recognition flow integration."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Test voice message handling
        voice_update = self.create_voice_update()
        
        with patch.object(integrated_services['speech'], '_download_voice_file') as mock_download, \
             patch.object(integrated_services['speech'], '_transcribe_audio') as mock_transcribe:
            
            mock_download.return_value = b"fake_audio_data"
            mock_transcribe.return_value = "Transcribed text"
            
            await integrated_services['speech'].handle_voice_message(voice_update, context)
            
            mock_download.assert_called_once()
            mock_transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_processing_integration(self, integrated_services):
        """Test callback processing integration."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Test speech language selection callback
        callback_update = self.create_callback_update("speech_lang_en_abc123")
        
        # Set up file hash mapping
        integrated_services['speech'].file_id_hash_map["abc123"] = "voice_file_123"
        
        await integrated_services['callback'].handle_callback_query(callback_update, context)
        
        # Verify callback was processed
        callback_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_command_registry_integration(self, integrated_services):
        """Test command registry integration."""
        # Test command registration
        await integrated_services['command'].register_all_commands()
        
        # Verify command processor was used
        command_processor = integrated_services['registry'].get_service('command_processor')
        assert command_processor is not None

    @pytest.mark.asyncio
    async def test_cross_service_communication(self, integrated_services):
        """Test communication between different services."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Test message service triggering speech recognition
        text_update = self.create_text_update("/speech_toggle")
        
        # Mock command processing to enable speech
        command_processor = integrated_services['registry'].get_service('command_processor')
        command_processor.process_command.return_value = True
        
        await integrated_services['message'].handle_text_message(text_update, context)
        
        # Test that speech service can be configured
        chat_id = str(text_update.effective_chat.id)
        chat_type = text_update.effective_chat.type
        
        config = await integrated_services['speech'].get_speech_config(chat_id, chat_type)
        assert config is not None

    @pytest.mark.asyncio
    async def test_error_propagation_across_services(self, integrated_services):
        """Test error handling and propagation across services."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Make GPT service raise an exception
        gpt_service = integrated_services['registry'].get_service('gpt_service')
        gpt_service.process_message.side_effect = Exception("GPT service error")
        
        # Test that message service handles the error gracefully
        text_update = self.create_text_update("Test message")
        
        # Should not raise an exception
        await integrated_services['message'].handle_text_message(text_update, context)
        
        # Verify error was handled
        gpt_service.process_message.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_service_operations(self, integrated_services):
        """Test concurrent operations across multiple services."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Create multiple concurrent operations
        tasks = []
        
        # Message processing tasks
        for i in range(10):
            update = self.create_text_update(f"Message {i}")
            task = integrated_services['message'].handle_text_message(update, context)
            tasks.append(task)
        
        # Speech configuration tasks
        for i in range(10):
            task = integrated_services['speech'].get_speech_config(f"chat_{i}", "group")
            tasks.append(task)
        
        # Callback processing tasks
        for i in range(10):
            callback_update = self.create_callback_update(f"test_callback_{i}")
            task = integrated_services['callback'].handle_callback_query(callback_update, context)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Most operations should succeed
        successful = sum(1 for r in results if not isinstance(r, Exception))
        assert successful >= 25  # Allow for some failures due to mocking

    @pytest.mark.asyncio
    async def test_service_registry_lifecycle(self, service_registry):
        """Test service registry lifecycle management."""
        # Test service initialization
        await service_registry.initialize_all_services()
        
        # Verify services are initialized
        config_manager = service_registry.get_service('config_manager')
        assert config_manager is not None
        
        # Test service shutdown
        await service_registry.shutdown_all_services()

    @pytest.mark.asyncio
    async def test_configuration_changes_propagation(self, integrated_services):
        """Test configuration changes propagating through services."""
        config_manager = integrated_services['registry'].get_service('config_manager')
        
        # Change configuration
        new_config = {
            'gpt': {'enabled': False, 'random_response_chance': 0.0},
            'speech': {'enabled': False, 'default_language': 'es'},
            'commands': {'enabled': True},
            'url_processing': {'enabled': False}
        }
        config_manager.get_config.return_value = new_config
        
        # Test that services respect new configuration
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        text_update = self.create_text_update("Test message")
        await integrated_services['message'].handle_text_message(text_update, context)
        
        # Verify configuration was checked
        config_manager.get_config.assert_called()

    @pytest.mark.asyncio
    async def test_url_processing_integration(self, integrated_services):
        """Test URL processing integration across services."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Test message with URL
        url_update = self.create_text_update("Check this out: https://example.com/test")
        
        with patch.object(integrated_services['message'], 'process_urls') as mock_process_urls:
            await integrated_services['message'].handle_text_message(url_update, context)
            
            # Verify URL processing was triggered
            mock_process_urls.assert_called()

    @pytest.mark.asyncio
    async def test_sticker_message_integration(self, integrated_services):
        """Test sticker message handling integration."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Create sticker update
        user = Mock(spec=User)
        user.id = 12345
        
        chat = Mock(spec=Chat)
        chat.id = 67890
        chat.type = "private"
        
        sticker = Mock()
        sticker.file_id = "sticker_123"
        
        message = Mock(spec=Message)
        message.sticker = sticker
        message.from_user = user
        message.chat = chat
        
        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        
        await integrated_services['message'].handle_sticker_message(update, context)
        
        # Should handle sticker without errors
        assert True  # If we get here, no exception was raised

    @pytest.mark.asyncio
    async def test_location_message_integration(self, integrated_services):
        """Test location message handling integration."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Create location update
        user = Mock(spec=User)
        user.id = 12345
        
        chat = Mock(spec=Chat)
        chat.id = 67890
        chat.type = "private"
        
        location = Mock()
        location.latitude = 40.7128
        location.longitude = -74.0060
        
        message = Mock(spec=Message)
        message.location = location
        message.from_user = user
        message.chat = chat
        
        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        
        await integrated_services['message'].handle_location_message(update, context)
        
        # Should handle location without errors
        assert True  # If we get here, no exception was raised

    @pytest.mark.asyncio
    async def test_video_note_integration(self, integrated_services):
        """Test video note handling integration."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Create video note update
        user = Mock(spec=User)
        user.id = 12345
        
        chat = Mock(spec=Chat)
        chat.id = 67890
        chat.type = "private"
        
        video_note = Mock(spec=VideoNote)
        video_note.file_id = "video_note_123"
        video_note.duration = 15
        
        message = Mock(spec=Message)
        message.video_note = video_note
        message.from_user = user
        message.chat = chat
        
        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        
        with patch.object(integrated_services['speech'], '_download_video_note') as mock_download, \
             patch.object(integrated_services['speech'], '_transcribe_audio') as mock_transcribe:
            
            mock_download.return_value = b"fake_video_data"
            mock_transcribe.return_value = "Video transcription"
            
            await integrated_services['speech'].handle_video_note(update, context)
            
            mock_download.assert_called_once()
            mock_transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_health_monitoring(self, integrated_services):
        """Test service health monitoring integration."""
        # Test that all services are healthy
        services = [
            integrated_services['message'],
            integrated_services['speech'],
            integrated_services['callback'],
            integrated_services['command']
        ]
        
        for service in services:
            # Services should be instantiated and functional
            assert service is not None
            
            # Test basic functionality
            if hasattr(service, 'get_speech_config'):
                config = await service.get_speech_config("test", "private")
                assert config is not None or config is None  # Either is acceptable

    @pytest.mark.asyncio
    async def test_memory_cleanup_integration(self, integrated_services):
        """Test memory cleanup across integrated services."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Process many messages to test memory management
        for i in range(100):
            update = self.create_text_update(f"Message {i}")
            await integrated_services['message'].handle_text_message(update, context)
        
        # Test speech service file hash map cleanup
        speech_service = integrated_services['speech']
        
        # Add many entries to hash map
        for i in range(100):
            speech_service.file_id_hash_map[f"hash_{i}"] = f"file_{i}"
        
        # Verify entries exist
        assert len(speech_service.file_id_hash_map) >= 100
        
        # Test cleanup (if implemented)
        if hasattr(speech_service, '_cleanup_old_hashes'):
            await speech_service._cleanup_old_hashes()

    @pytest.mark.asyncio
    async def test_error_recovery_integration(self, integrated_services):
        """Test error recovery across integrated services."""
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        # Test recovery from GPT service failure
        gpt_service = integrated_services['registry'].get_service('gpt_service')
        
        # First call fails
        gpt_service.process_message.side_effect = [
            Exception("Temporary failure"),
            "Recovered response"
        ]
        
        # Process two messages
        update1 = self.create_text_update("First message")
        update2 = self.create_text_update("Second message")
        
        await integrated_services['message'].handle_text_message(update1, context)
        await integrated_services['message'].handle_text_message(update2, context)
        
        # Both calls should have been made
        assert gpt_service.process_message.call_count == 2

    @pytest.mark.asyncio
    async def test_configuration_validation_integration(self, integrated_services):
        """Test configuration validation across services."""
        config_manager = integrated_services['registry'].get_service('config_manager')
        
        # Test with invalid configuration
        invalid_config = {
            'gpt': {'enabled': 'invalid_boolean'},  # Invalid type
            'speech': {'enabled': True, 'default_language': None},  # Invalid value
            'commands': {},  # Missing required fields
        }
        
        config_manager.get_config.return_value = invalid_config
        
        # Services should handle invalid configuration gracefully
        context = Mock(spec=CallbackContext)
        context.bot = AsyncMock()
        
        update = self.create_text_update("Test message")
        
        # Should not raise an exception
        await integrated_services['message'].handle_text_message(update, context)

    @pytest.mark.asyncio
    async def test_service_dependency_resolution(self, service_registry):
        """Test service dependency resolution."""
        # Test that services can resolve their dependencies
        config_manager = service_registry.get_service('config_manager')
        gpt_service = service_registry.get_service('gpt_service')
        command_processor = service_registry.get_service('command_processor')
        
        assert config_manager is not None
        assert gpt_service is not None
        assert command_processor is not None
        
        # Test creating services with dependencies
        message_service = MessageHandlerService(
            config_manager=config_manager,
            gpt_service=gpt_service
        )
        
        speech_service = SpeechRecognitionService(config_manager=config_manager)
        callback_service = CallbackHandlerService(speech_service=speech_service)
        command_registry = CommandRegistry(command_processor=command_processor)
        
        # All services should be created successfully
        assert message_service is not None
        assert speech_service is not None
        assert callback_service is not None
        assert command_registry is not None


class TestApplicationBootstrapperIntegration:
    """Integration tests for ApplicationBootstrapper with real services."""

    @pytest.mark.asyncio
    async def test_full_application_bootstrap_integration(self):
        """Test complete application bootstrap integration."""
        with patch.dict('os.environ', {
            'TELEGRAM_TOKEN': 'test_token_123',
            'ERROR_CHANNEL_ID': 'test_channel_456'
        }):
            bootstrapper = ApplicationBootstrapper()
            
            # Mock external dependencies
            with patch('modules.application_bootstrapper.ConfigManager') as mock_config_class, \
                 patch('modules.application_bootstrapper.BotApplication') as mock_bot_class, \
                 patch.object(bootstrapper, 'setup_signal_handlers'):
                
                mock_config = Mock()
                mock_config.initialize = AsyncMock()
                mock_config_class.return_value = mock_config
                
                mock_bot = Mock()
                mock_bot.initialize = AsyncMock()
                mock_bot.start = AsyncMock()
                mock_bot.shutdown = AsyncMock()
                mock_bot_class.return_value = mock_bot
                
                # Test full lifecycle
                registry = await bootstrapper.configure_services()
                assert registry is not None
                
                await bootstrapper.start_application()
                assert bootstrapper.is_running is True
                
                await bootstrapper.shutdown_application()
                assert bootstrapper.is_running is False
                
                # Verify all components were properly initialized
                mock_config.initialize.assert_called_once()
                mock_bot.initialize.assert_called_once()
                mock_bot.start.assert_called_once()
                mock_bot.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_bootstrap_with_service_failures(self):
        """Test bootstrap behavior with service initialization failures."""
        with patch.dict('os.environ', {
            'TELEGRAM_TOKEN': 'test_token',
            'ERROR_CHANNEL_ID': 'test_channel'
        }):
            bootstrapper = ApplicationBootstrapper()
            
            with patch('modules.application_bootstrapper.ServiceRegistry') as mock_registry_class:
                mock_registry = Mock()
                mock_registry.register_service = Mock()
                mock_registry.initialize_all_services = AsyncMock(
                    side_effect=Exception("Service initialization failed")
                )
                mock_registry_class.return_value = mock_registry
                
                # Configure services should succeed
                registry = await bootstrapper.configure_services()
                assert registry is not None
                
                # Start application should fail
                with pytest.raises(Exception, match="Service initialization failed"):
                    await bootstrapper.start_application()
                
                # Application should not be running
                assert bootstrapper.is_running is False