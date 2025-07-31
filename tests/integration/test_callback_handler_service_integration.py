"""
Integration tests for CallbackHandlerService.

Tests the callback handler service integration with other services and
real Telegram callback scenarios including end-to-end callback processing.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, CallbackQuery, Message, Chat, User
from telegram.ext import CallbackContext

from modules.callback_handler_service import CallbackHandlerService
from modules.speech_recognition_service import SpeechRecognitionService
from config.config_manager import ConfigManager


class TestCallbackHandlerServiceIntegration:
    """Integration tests for CallbackHandlerService."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock(return_value={
            "config_modules": {
                "speechmatics": {
                    "enabled": True
                }
            }
        })
        return config_manager
        
    @pytest.fixture
    def speech_service(self, mock_config_manager):
        """Create speech recognition service."""
        return SpeechRecognitionService(mock_config_manager)
        
    @pytest.fixture
    def callback_service(self, speech_service):
        """Create callback handler service with speech service."""
        return CallbackHandlerService(speech_service=speech_service)
        
    @pytest.fixture
    def mock_telegram_update(self):
        """Create realistic Telegram update with callback query."""
        from unittest.mock import Mock
        
        user = Mock()
        user.id = 123
        user.first_name = "Test"
        user.is_bot = False
        
        chat = Mock()
        chat.id = 456
        chat.type = "private"
        
        message = Mock()
        message.message_id = 789
        message.chat = chat
        message.from_user = user
        
        query = Mock()
        query.id = "callback_123"
        query.from_user = user
        query.chat_instance = "chat_instance_123"
        query.data = "test_callback"
        query.message = message
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        
        update = Mock()
        update.update_id = 1
        update.callback_query = query
        update.effective_chat = chat
        
        return update
        
    @pytest.fixture
    def mock_telegram_context(self):
        """Create realistic Telegram callback context."""
        context = Mock(spec=CallbackContext)
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        context.bot_data = {"abcd1234": "https://example.com/test"}
        return context
        
    @pytest.mark.asyncio
    async def test_service_initialization_and_shutdown(self, callback_service):
        """Test service lifecycle management."""
        # Test initialization
        await callback_service.initialize()
        
        # Service should be ready
        assert callback_service.speech_service is not None
        
        # Test shutdown
        await callback_service.shutdown()
        
        # Cleanup should be complete
        assert len(callback_service.callback_timestamps) == 0
        
    @pytest.mark.asyncio
    async def test_end_to_end_test_callback(self, callback_service, mock_telegram_update, mock_telegram_context):
        """Test end-to-end test callback processing."""
        mock_telegram_update.callback_query.data = "test_callback"
        
        await callback_service.handle_callback_query(mock_telegram_update, mock_telegram_context)
        
        # Verify callback was answered
        mock_telegram_update.callback_query.answer.assert_called_once()
        
        # Verify response was sent
        mock_telegram_update.callback_query.edit_message_text.assert_called_once_with(
            "✅ Test callback received and handled!"
        )
        
    @pytest.mark.asyncio
    @patch('modules.speech_recognition_service.transcribe_telegram_voice')
    async def test_end_to_end_speech_recognition_callback(
        self, 
        mock_transcribe,
        callback_service, 
        mock_telegram_update, 
        mock_telegram_context
    ):
        """Test end-to-end speech recognition callback processing."""
        # Setup speech recognition callback
        mock_telegram_update.callback_query.data = "speechrec_abcd1234"
        
        # Setup file ID mapping in speech service
        callback_service.speech_service.file_id_hash_map["abcd1234"] = "test_file_id"
        
        # Mock successful transcription
        mock_transcribe.return_value = "Hello world"
        
        await callback_service.handle_callback_query(mock_telegram_update, mock_telegram_context)
        
        # Verify callback was answered (may be called multiple times by different services)
        assert mock_telegram_update.callback_query.answer.call_count >= 1
        
        # Verify progress message was shown
        mock_telegram_update.callback_query.edit_message_text.assert_called_with(
            "🔄 Recognizing speech, please wait..."
        )
        
        # Verify transcription was called
        mock_transcribe.assert_called_once_with(
            mock_telegram_context.bot, 
            "test_file_id", 
            language="auto"
        )
        
        # Verify result was sent
        mock_telegram_context.bot.send_message.assert_called_once_with(
            chat_id=456,
            text="🗣️ Recognized speech:\nHello world"
        )
        
    @pytest.mark.asyncio
    @patch('modules.speech_recognition_service.transcribe_telegram_voice')
    async def test_end_to_end_language_selection_callback(
        self,
        mock_transcribe,
        callback_service,
        mock_telegram_update,
        mock_telegram_context
    ):
        """Test end-to-end language selection callback processing."""
        # Setup language selection callback
        mock_telegram_update.callback_query.data = "lang_en|abcd1234"
        
        # Setup file ID mapping in speech service
        callback_service.speech_service.file_id_hash_map["abcd1234"] = "test_file_id"
        
        # Mock successful transcription
        mock_transcribe.return_value = "Hello world"
        
        await callback_service.handle_callback_query(mock_telegram_update, mock_telegram_context)
        
        # Verify callback was answered (may be called multiple times by different services)
        assert mock_telegram_update.callback_query.answer.call_count >= 1
        
        # Verify progress message was shown (check call history)
        calls = mock_telegram_update.callback_query.edit_message_text.call_args_list
        progress_call_found = any(
            "🔄 Processing with en language..." in str(call) 
            for call in calls
        )
        assert progress_call_found, f"Progress message not found in calls: {calls}"
        
        # Verify transcription was called with specific language
        mock_transcribe.assert_called_once_with(
            mock_telegram_context.bot,
            "test_file_id",
            language="en"
        )
        
    @pytest.mark.asyncio
    @patch('modules.keyboards.button_callback')
    async def test_end_to_end_link_modification_callback(
        self,
        mock_button_callback,
        callback_service,
        mock_telegram_update,
        mock_telegram_context
    ):
        """Test end-to-end link modification callback processing."""
        # Setup link modification callback
        mock_telegram_update.callback_query.data = "translate:abcd1234"
        mock_button_callback.return_value = AsyncMock()
        
        await callback_service.handle_callback_query(mock_telegram_update, mock_telegram_context)
        
        # Verify callback was answered
        mock_telegram_update.callback_query.answer.assert_called_once()
        
        # Verify delegation to button_callback
        mock_button_callback.assert_called_once_with(mock_telegram_update, mock_telegram_context)
        
    @pytest.mark.asyncio
    async def test_callback_validation_integration(self, callback_service):
        """Test callback validation with integrated services."""
        # Test valid speech recognition callback
        callback_service.speech_service.file_id_hash_map["abcd1234"] = "test_file_id"
        
        is_valid, error = callback_service.validate_callback_data("speechrec_abcd1234")
        assert is_valid
        assert error is None
        
        # Test invalid speech recognition callback
        is_valid, error = callback_service.validate_callback_data("speechrec_invalid")
        assert not is_valid
        assert "expired" in error.lower()
        
        # Test valid language selection callback
        is_valid, error = callback_service.validate_callback_data("lang_en|abcd1234")
        assert is_valid
        assert error is None
        
        # Test valid link modification callback
        is_valid, error = callback_service.validate_callback_data("translate:abcd1234")
        assert is_valid
        assert error is None
        
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, callback_service, mock_telegram_update, mock_telegram_context):
        """Test error handling across service boundaries."""
        # Test with invalid callback data
        mock_telegram_update.callback_query.data = "invalid_format"
        
        await callback_service.handle_callback_query(mock_telegram_update, mock_telegram_context)
        
        # Should handle gracefully
        mock_telegram_update.callback_query.answer.assert_called_once()
        mock_telegram_update.callback_query.edit_message_text.assert_called_once_with(
            "❌ Unknown callback action."
        )
        
    @pytest.mark.asyncio
    async def test_speech_service_integration_without_service(self, mock_telegram_update, mock_telegram_context):
        """Test callback handling without speech service."""
        callback_service = CallbackHandlerService(speech_service=None)
        
        # Test speech recognition callback without service
        mock_telegram_update.callback_query.data = "speechrec_abcd1234"
        
        await callback_service.handle_callback_query(mock_telegram_update, mock_telegram_context)
        
        mock_telegram_update.callback_query.answer.assert_called_once()
        mock_telegram_update.callback_query.edit_message_text.assert_called_once_with(
            "❌ Speech recognition service not available."
        )
        
    @pytest.mark.asyncio
    async def test_concurrent_callback_processing(self, callback_service, mock_telegram_context):
        """Test handling multiple concurrent callbacks."""
        # Create multiple updates
        updates = []
        for i in range(5):
            user = Mock()
            user.id = 123 + i
            user.first_name = f"Test{i}"
            user.is_bot = False
            
            chat = Mock()
            chat.id = 456 + i
            chat.type = "private"
            
            message = Mock()
            message.message_id = 789 + i
            message.chat = chat
            message.from_user = user
            
            query = Mock()
            query.id = f"callback_{i}"
            query.from_user = user
            query.chat_instance = f"chat_instance_{i}"
            query.data = "test_callback"
            query.message = message
            query.answer = AsyncMock()
            query.edit_message_text = AsyncMock()
            
            update = Mock()
            update.update_id = i
            update.callback_query = query
            update.effective_chat = chat
            updates.append(update)
            
        # Process all callbacks concurrently
        tasks = [
            callback_service.handle_callback_query(update, mock_telegram_context)
            for update in updates
        ]
        
        await asyncio.gather(*tasks)
        
        # Verify all callbacks were processed
        for update in updates:
            update.callback_query.answer.assert_called_once()
            update.callback_query.edit_message_text.assert_called_once_with(
                "✅ Test callback received and handled!"
            )
            
    @pytest.mark.asyncio
    async def test_callback_expiration_integration(self, callback_service):
        """Test callback expiration handling."""
        import time
        
        # Register a callback and make it expired
        callback_data = "test_callback"
        callback_service.callback_timestamps[callback_data] = time.time() - 7200  # 2 hours ago
        
        # Validation should detect expiration
        is_valid, error = callback_service.validate_callback_data(callback_data)
        assert not is_valid
        assert "expired" in error.lower()
        
        # Cleanup should remove expired callbacks
        callback_service._cleanup_expired_callbacks()
        assert callback_data not in callback_service.callback_timestamps
        
    @pytest.mark.asyncio
    async def test_service_dependency_injection(self, mock_config_manager):
        """Test service dependency injection patterns."""
        # Create services with proper dependency injection
        speech_service = SpeechRecognitionService(mock_config_manager)
        callback_service = CallbackHandlerService(speech_service=speech_service)
        
        # Verify dependencies are properly injected
        assert callback_service.speech_service == speech_service
        assert speech_service.config_manager == mock_config_manager
        
        # Test dynamic service setting
        new_speech_service = SpeechRecognitionService(mock_config_manager)
        callback_service.set_speech_service(new_speech_service)
        
        assert callback_service.speech_service == new_speech_service
        
    def test_callback_pattern_coverage(self, callback_service):
        """Test that all expected callback patterns are supported."""
        patterns = callback_service.get_supported_callback_patterns()
        
        # Verify all expected patterns are present
        expected_patterns = {
            r"^speechrec_",      # Speech recognition
            r"^lang_",           # Language selection
            r"^test_callback$",  # Test callbacks
            r"^[a-zA-Z_]+:[0-9a-f]+$"  # Link modifications
        }
        
        assert patterns == expected_patterns
        
        # Test pattern matching
        import re
        test_cases = [
            ("speechrec_abcd1234", True),
            ("lang_en|abcd1234", True),
            ("test_callback", True),
            ("translate:abcd1234", True),
            ("download_video:abcd1234", True),
            ("invalid_pattern", False),
            ("", False),
        ]
        
        for callback_data, should_match in test_cases:
            matches = any(re.match(pattern, callback_data) for pattern in patterns)
            assert matches == should_match, f"Pattern matching failed for: {callback_data}"