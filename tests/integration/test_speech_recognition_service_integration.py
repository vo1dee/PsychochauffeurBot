"""
Integration tests for SpeechRecognitionService.

This module contains integration tests that verify the SpeechRecognitionService
works correctly with real dependencies and in realistic scenarios.
"""

import pytest
import hashlib
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, Voice, VideoNote, CallbackQuery, Chat, User, Bot
from telegram.ext import CallbackContext

from modules.speech_recognition_service import SpeechRecognitionService
from config.config_manager import ConfigManager
from modules.service_registry import ServiceRegistry


@pytest.fixture
async def config_manager():
    """Create a real ConfigManager instance for integration testing."""
    config_manager = ConfigManager()
    await config_manager.initialize()
    yield config_manager
    # Cleanup
    if hasattr(config_manager, 'stop'):
        await config_manager.stop()


@pytest.fixture
def service_registry():
    """Create a ServiceRegistry for integration testing."""
    return ServiceRegistry()


@pytest.fixture
async def speech_service_integrated(config_manager, service_registry):
    """Create an integrated SpeechRecognitionService with real dependencies."""
    service = SpeechRecognitionService(config_manager=config_manager)
    await service.initialize()
    
    # Register with service registry
    service_registry.register_instance('speech_recognition_service', service)
    
    yield service
    
    # Cleanup
    await service.shutdown()


@pytest.fixture
def mock_telegram_update():
    """Create a realistic Telegram update for integration testing."""
    update = Mock(spec=Update)
    update.effective_chat = Mock(spec=Chat)
    update.effective_chat.id = 12345
    update.effective_chat.type = "group"
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 67890
    update.message = Mock(spec=Message)
    update.message.from_user = update.effective_user
    return update


@pytest.fixture
def mock_telegram_context():
    """Create a realistic Telegram context for integration testing."""
    context = Mock(spec=CallbackContext)
    context.bot = Mock(spec=Bot)
    context.bot.send_message = AsyncMock()
    return context


class TestSpeechRecognitionServiceIntegration:
    """Integration tests for SpeechRecognitionService with real dependencies."""
    
    @pytest.mark.asyncio
    async def test_service_lifecycle_integration(self, config_manager):
        """Test complete service lifecycle with real config manager."""
        service = SpeechRecognitionService(config_manager=config_manager)
        
        # Test initialization
        await service.initialize()
        assert service.config_manager is config_manager
        assert isinstance(service.file_id_hash_map, dict)
        
        # Test shutdown
        await service.shutdown()
        assert len(service.file_id_hash_map) == 0
        
    @pytest.mark.asyncio
    async def test_speech_configuration_integration(self, speech_service_integrated):
        """Test speech configuration management with real config manager."""
        chat_id = "test_chat_12345"
        chat_type = "group"
        
        # Test initial state (should be disabled)
        is_enabled = await speech_service_integrated.is_speech_enabled(chat_id, chat_type)
        assert is_enabled is False
        
        # Enable speech recognition
        await speech_service_integrated.toggle_speech_recognition(chat_id, chat_type, True)
        
        # Verify it's enabled
        is_enabled = await speech_service_integrated.is_speech_enabled(chat_id, chat_type)
        assert is_enabled is True
        
        # Get config and verify structure
        config = await speech_service_integrated.get_speech_config(chat_id, chat_type)
        assert config is not None
        assert config.get("enabled") is True
        assert "overrides" in config
        
        # Disable speech recognition
        await speech_service_integrated.toggle_speech_recognition(chat_id, chat_type, False)
        
        # Verify it's disabled
        is_enabled = await speech_service_integrated.is_speech_enabled(chat_id, chat_type)
        assert is_enabled is False
        
    @pytest.mark.asyncio
    async def test_voice_message_flow_integration(self, speech_service_integrated, mock_telegram_update, mock_telegram_context):
        """Test complete voice message processing flow."""
        # Setup voice message
        mock_telegram_update.message.voice = Mock(spec=Voice)
        mock_telegram_update.message.voice.file_id = "voice_file_integration_test"
        mock_telegram_update.message.reply_text = AsyncMock()
        
        # Enable speech recognition for this chat
        chat_id = str(mock_telegram_update.effective_chat.id)
        chat_type = mock_telegram_update.effective_chat.type
        await speech_service_integrated.toggle_speech_recognition(chat_id, chat_type, True)
        
        # Process voice message
        await speech_service_integrated.handle_voice_message(mock_telegram_update, mock_telegram_context)
        
        # Verify button was sent
        mock_telegram_update.message.reply_text.assert_called_once()
        args, kwargs = mock_telegram_update.message.reply_text.call_args
        assert "Press the button to recognize speech" in args[0]
        assert kwargs['reply_markup'] is not None
        
        # Verify file hash was stored
        file_id = "voice_file_integration_test"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        assert speech_service_integrated.file_id_hash_map[file_hash] == file_id
        
    @pytest.mark.asyncio
    async def test_video_note_flow_integration(self, speech_service_integrated, mock_telegram_update, mock_telegram_context):
        """Test complete video note processing flow."""
        # Setup video note message
        mock_telegram_update.message.video_note = Mock(spec=VideoNote)
        mock_telegram_update.message.video_note.file_id = "video_note_integration_test"
        mock_telegram_update.message.reply_text = AsyncMock()
        
        # Enable speech recognition for this chat
        chat_id = str(mock_telegram_update.effective_chat.id)
        chat_type = mock_telegram_update.effective_chat.type
        await speech_service_integrated.toggle_speech_recognition(chat_id, chat_type, True)
        
        # Process video note message
        await speech_service_integrated.handle_video_note(mock_telegram_update, mock_telegram_context)
        
        # Verify button was sent
        mock_telegram_update.message.reply_text.assert_called_once()
        args, kwargs = mock_telegram_update.message.reply_text.call_args
        assert "Press the button to recognize speech" in args[0]
        assert kwargs['reply_markup'] is not None
        
        # Verify file hash was stored
        file_id = "video_note_integration_test"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        assert speech_service_integrated.file_id_hash_map[file_hash] == file_id
        
    @pytest.mark.asyncio
    async def test_callback_processing_integration(self, speech_service_integrated, mock_telegram_context):
        """Test callback processing with real service state."""
        # Setup file hash mapping
        file_id = "test_file_callback_integration"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        speech_service_integrated.file_id_hash_map[file_hash] = file_id
        
        # Create callback update
        update = Mock(spec=Update)
        update.callback_query = Mock(spec=CallbackQuery)
        update.callback_query.data = f"speechrec_{file_hash}"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 12345
        
        # Mock the transcription
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            mock_transcribe.return_value = "Integration test transcript"
            
            await speech_service_integrated.process_speech_recognition(update, mock_telegram_context)
            
            # Verify transcription was called
            mock_transcribe.assert_called_once_with(mock_telegram_context.bot, file_id, language="auto")
            
            # Verify message was sent
            mock_telegram_context.bot.send_message.assert_called_once_with(
                chat_id=12345,
                text="🗣️ Recognized speech:\nIntegration test transcript"
            )
            
    @pytest.mark.asyncio
    async def test_language_selection_integration(self, speech_service_integrated, mock_telegram_context):
        """Test language selection callback processing."""
        # Setup file hash mapping
        file_id = "test_file_language_integration"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        speech_service_integrated.file_id_hash_map[file_hash] = file_id
        
        # Create language selection callback update
        update = Mock(spec=Update)
        update.callback_query = Mock(spec=CallbackQuery)
        update.callback_query.data = f"lang_en|{file_hash}"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        
        # Mock the transcription
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            mock_transcribe.return_value = "English transcript"
            
            await speech_service_integrated.handle_language_selection(update, mock_telegram_context)
            
            # Verify transcription was called with correct language
            mock_transcribe.assert_called_once_with(mock_telegram_context.bot, file_id, language="en")
            
            # Verify response was edited
            update.callback_query.edit_message_text.assert_called_once_with(
                "🗣️ Recognized (en):\nEnglish transcript"
            )
            
    @pytest.mark.asyncio
    async def test_callback_data_validation_integration(self, speech_service_integrated):
        """Test callback data validation with real service state."""
        # Test valid speechrec callback
        file_hash = "valid_hash_123"
        speech_service_integrated.file_id_hash_map[file_hash] = "file_id"
        
        is_valid, error = speech_service_integrated.validate_callback_data(f"speechrec_{file_hash}")
        assert is_valid is True
        assert error is None
        
        # Test valid language callback
        is_valid, error = speech_service_integrated.validate_callback_data(f"lang_en|{file_hash}")
        assert is_valid is True
        assert error is None
        
        # Test expired callback
        is_valid, error = speech_service_integrated.validate_callback_data("speechrec_expired_hash")
        assert is_valid is False
        assert error == "Speech recognition button has expired"
        
        # Test invalid format
        is_valid, error = speech_service_integrated.validate_callback_data("invalid_format")
        assert is_valid is False
        assert error == "Invalid callback data format"
        
    @pytest.mark.asyncio
    async def test_service_registry_integration(self, service_registry, config_manager):
        """Test integration with ServiceRegistry."""
        # Register the service
        service_registry.register_singleton(
            'speech_recognition_service',
            SpeechRecognitionService,
            dependencies=['config_manager']
        )
        service_registry.register_instance('config_manager', config_manager)
        
        # Initialize services
        await service_registry.initialize_services()
        
        # Get the service
        service = service_registry.get_service('speech_recognition_service')
        assert isinstance(service, SpeechRecognitionService)
        assert service.config_manager is config_manager
        
        # Test service functionality
        is_enabled = await service.is_speech_enabled("test_chat", "group")
        assert is_enabled is False
        
        # Cleanup
        await service_registry.shutdown_services()
        
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, speech_service_integrated, mock_telegram_context):
        """Test error handling in integration scenarios."""
        # Setup file hash mapping
        file_id = "test_file_error_integration"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        speech_service_integrated.file_id_hash_map[file_hash] = file_id
        
        # Create callback update
        update = Mock(spec=Update)
        update.callback_query = Mock(spec=CallbackQuery)
        update.callback_query.data = f"speechrec_{file_hash}"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 12345
        
        # Mock transcription to raise an exception
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            mock_transcribe.side_effect = Exception("API Error")
            
            await speech_service_integrated.process_speech_recognition(update, mock_telegram_context)
            
            # Verify error message was sent
            mock_telegram_context.bot.send_message.assert_called_once_with(
                chat_id=12345,
                text="❌ Speech recognition failed: API Error"
            )
            
    @pytest.mark.asyncio
    async def test_concurrent_operations_integration(self, speech_service_integrated, mock_telegram_context):
        """Test concurrent operations on the service."""
        import asyncio
        
        # Setup multiple file hash mappings
        file_ids = [f"concurrent_file_{i}" for i in range(5)]
        file_hashes = []
        
        for file_id in file_ids:
            file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
            speech_service_integrated.file_id_hash_map[file_hash] = file_id
            file_hashes.append(file_hash)
        
        # Create multiple callback updates
        updates = []
        for i, file_hash in enumerate(file_hashes):
            update = Mock(spec=Update)
            update.callback_query = Mock(spec=CallbackQuery)
            update.callback_query.data = f"speechrec_{file_hash}"
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            update.effective_chat = Mock(spec=Chat)
            update.effective_chat.id = 12345 + i
            updates.append(update)
        
        # Mock transcription
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            mock_transcribe.return_value = "Concurrent transcript"
            
            # Process all callbacks concurrently
            tasks = [
                speech_service_integrated.process_speech_recognition(update, mock_telegram_context)
                for update in updates
            ]
            
            await asyncio.gather(*tasks)
            
            # Verify all transcriptions were called
            assert mock_transcribe.call_count == 5
            assert mock_telegram_context.bot.send_message.call_count == 5
            
    @pytest.mark.asyncio
    async def test_configuration_persistence_integration(self, speech_service_integrated):
        """Test that configuration changes persist correctly."""
        chat_id = "persistence_test_chat"
        chat_type = "group"
        
        # Initially disabled
        assert await speech_service_integrated.is_speech_enabled(chat_id, chat_type) is False
        
        # Enable and verify
        await speech_service_integrated.toggle_speech_recognition(chat_id, chat_type, True)
        assert await speech_service_integrated.is_speech_enabled(chat_id, chat_type) is True
        
        # Create a new service instance with the same config manager
        new_service = SpeechRecognitionService(config_manager=speech_service_integrated.config_manager)
        await new_service.initialize()
        
        # Verify configuration persisted
        assert await new_service.is_speech_enabled(chat_id, chat_type) is True
        
        # Cleanup
        await new_service.shutdown()


class TestSpeechRecognitionServiceEdgeCasesIntegration:
    """Integration tests for edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_large_file_hash_map_integration(self, speech_service_integrated):
        """Test service behavior with large number of file hash mappings."""
        # Add many file hash mappings
        for i in range(1000):
            file_id = f"large_test_file_{i}"
            file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
            speech_service_integrated.file_id_hash_map[file_hash] = file_id
        
        # Verify all mappings exist
        assert len(speech_service_integrated.file_id_hash_map) == 1000
        
        # Test validation still works
        test_hash = hashlib.md5("large_test_file_500".encode()).hexdigest()[:16]
        is_valid, error = speech_service_integrated.validate_callback_data(f"speechrec_{test_hash}")
        assert is_valid is True
        assert error is None
        
        # Test cleanup
        await speech_service_integrated.shutdown()
        assert len(speech_service_integrated.file_id_hash_map) == 0
        
    @pytest.mark.asyncio
    async def test_malformed_configuration_integration(self, config_manager):
        """Test service behavior with malformed configuration."""
        service = SpeechRecognitionService(config_manager=config_manager)
        await service.initialize()
        
        # Test with non-existent chat
        config = await service.get_speech_config("non_existent_chat", "group")
        assert config is None
        
        is_enabled = await service.is_speech_enabled("non_existent_chat", "group")
        assert is_enabled is False
        
        # Test enabling for non-existent chat (should create config)
        await service.toggle_speech_recognition("non_existent_chat", "group", True)
        is_enabled = await service.is_speech_enabled("non_existent_chat", "group")
        assert is_enabled is True
        
        await service.shutdown()
        
    @pytest.mark.asyncio
    async def test_hash_collision_handling_integration(self, speech_service_integrated):
        """Test handling of potential hash collisions."""
        # This is a theoretical test since MD5 collisions are rare
        # but we test the behavior when the same hash is used
        
        file_hash = "collision_test_hash"
        original_file_id = "original_file"
        new_file_id = "new_file"
        
        # Set original mapping
        speech_service_integrated.file_id_hash_map[file_hash] = original_file_id
        
        # Overwrite with new mapping (simulating collision handling)
        speech_service_integrated.file_id_hash_map[file_hash] = new_file_id
        
        # Verify the new mapping is used
        assert speech_service_integrated.file_id_hash_map[file_hash] == new_file_id
        
        # Test validation uses the current mapping
        is_valid, error = speech_service_integrated.validate_callback_data(f"speechrec_{file_hash}")
        assert is_valid is True
        assert error is None