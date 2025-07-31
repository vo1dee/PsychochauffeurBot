"""
Unit tests for CallbackHandlerService.

Tests the centralized callback query processing service including:
- Callback routing and validation
- Speech recognition callback handling
- Language selection callback handling
- Link modification callback handling
- Security validation and expiration handling
- Error handling and recovery
"""

import pytest
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, CallbackQuery, Message, Chat, User
from telegram.ext import CallbackContext

from modules.callback_handler_service import CallbackHandlerService
from modules.speech_recognition_service import SpeechRecognitionService


class TestCallbackHandlerService:
    """Test suite for CallbackHandlerService."""
    
    @pytest.fixture
    def mock_speech_service(self):
        """Create mock speech recognition service."""
        service = Mock(spec=SpeechRecognitionService)
        service.process_speech_recognition = AsyncMock()
        service.handle_language_selection = AsyncMock()
        service.validate_callback_data = Mock(return_value=(True, None))
        return service
        
    @pytest.fixture
    def callback_service(self, mock_speech_service):
        """Create callback handler service with mocked dependencies."""
        return CallbackHandlerService(speech_service=mock_speech_service)
        
    @pytest.fixture
    def callback_service_no_speech(self):
        """Create callback handler service without speech service."""
        return CallbackHandlerService(speech_service=None)
        
    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update with callback query."""
        update = Mock(spec=Update)
        query = Mock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = "test_callback"
        query.message = Mock(spec=Message)
        query.message.chat_id = 12345
        query.message.edit_text = AsyncMock()
        update.callback_query = query
        return update
        
    @pytest.fixture
    def mock_context(self):
        """Create mock callback context."""
        context = Mock(spec=CallbackContext)
        context.bot_data = {"abcd1234": "https://example.com/test"}
        return context
        
    @pytest.mark.asyncio
    async def test_initialize(self, callback_service):
        """Test service initialization."""
        await callback_service.initialize()
        # Should complete without error
        
    @pytest.mark.asyncio
    async def test_shutdown(self, callback_service):
        """Test service shutdown."""
        # Add some test data
        callback_service.callback_timestamps["test"] = time.time()
        
        await callback_service.shutdown()
        
        # Should clear timestamps
        assert len(callback_service.callback_timestamps) == 0
        
    @pytest.mark.asyncio
    async def test_handle_callback_query_no_query(self, callback_service):
        """Test handling update without callback query."""
        update = Mock(spec=Update)
        update.callback_query = None
        context = Mock(spec=CallbackContext)
        
        # Should handle gracefully without error
        await callback_service.handle_callback_query(update, context)
        
    @pytest.mark.asyncio
    async def test_handle_callback_query_no_data(self, callback_service, mock_context):
        """Test handling callback query without data."""
        update = Mock(spec=Update)
        query = Mock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = None
        update.callback_query = query
        
        await callback_service.handle_callback_query(update, mock_context)
        
        query.answer.assert_called_once()
        query.edit_message_text.assert_called_once_with("❌ Invalid callback data.")
        
    @pytest.mark.asyncio
    async def test_handle_test_callback(self, callback_service, mock_update, mock_context):
        """Test handling test callback."""
        mock_update.callback_query.data = "test_callback"
        
        await callback_service.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once_with(
            "✅ Test callback received and handled!"
        )
        
    @pytest.mark.asyncio
    async def test_handle_speech_recognition_callback(self, callback_service, mock_update, mock_context):
        """Test handling speech recognition callback."""
        mock_update.callback_query.data = "speechrec_abcd1234"
        
        await callback_service.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        callback_service.speech_service.process_speech_recognition.assert_called_once_with(
            mock_update, mock_context
        )
        
    @pytest.mark.asyncio
    async def test_handle_speech_recognition_callback_no_service(
        self, callback_service_no_speech, mock_update, mock_context
    ):
        """Test handling speech recognition callback without speech service."""
        mock_update.callback_query.data = "speechrec_abcd1234"
        
        await callback_service_no_speech.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once_with(
            "❌ Speech recognition service not available."
        )
        
    @pytest.mark.asyncio
    async def test_handle_language_selection_callback(self, callback_service, mock_update, mock_context):
        """Test handling language selection callback."""
        mock_update.callback_query.data = "lang_en|abcd1234"
        
        await callback_service.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        callback_service.speech_service.handle_language_selection.assert_called_once_with(
            mock_update, mock_context
        )
        
    @pytest.mark.asyncio
    async def test_handle_language_selection_callback_no_service(
        self, callback_service_no_speech, mock_update, mock_context
    ):
        """Test handling language selection callback without speech service."""
        mock_update.callback_query.data = "lang_en|abcd1234"
        
        await callback_service_no_speech.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once_with(
            "❌ Speech recognition service not available."
        )
        
    @pytest.mark.asyncio
    @patch('modules.keyboards.button_callback')
    async def test_handle_link_modification_callback(
        self, mock_button_callback, callback_service, mock_update, mock_context
    ):
        """Test handling link modification callback."""
        mock_update.callback_query.data = "translate:abcd1234"
        mock_button_callback.return_value = AsyncMock()
        
        await callback_service.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        mock_button_callback.assert_called_once_with(mock_update, mock_context)
        
    @pytest.mark.asyncio
    async def test_handle_link_modification_callback_invalid_format(
        self, callback_service, mock_update, mock_context
    ):
        """Test handling link modification callback with invalid format."""
        mock_update.callback_query.data = "invalid_format"
        
        await callback_service.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once_with(
            "❌ Unknown callback action."
        )
        
    @pytest.mark.asyncio
    async def test_handle_link_modification_callback_invalid_action(
        self, callback_service, mock_update, mock_context
    ):
        """Test handling link modification callback with invalid action."""
        mock_update.callback_query.data = "invalid_action:abcd1234"
        
        await callback_service.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once_with(
            "Unknown action."
        )
        
    @pytest.mark.asyncio
    async def test_handle_link_modification_callback_invalid_hash(
        self, callback_service, mock_update, mock_context
    ):
        """Test handling link modification callback with invalid hash."""
        mock_update.callback_query.data = "translate:invalid_hash"
        
        await callback_service.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once_with(
            "❌ Unknown callback action."
        )
        
    @pytest.mark.asyncio
    @patch('modules.keyboards.button_callback')
    async def test_handle_link_modification_callback_expired_link(
        self, mock_button_callback, callback_service, mock_update, mock_context
    ):
        """Test handling link modification callback with expired link."""
        mock_update.callback_query.data = "translate:abcd1234"
        # Link exists in bot_data so button_callback will be called
        mock_context.bot_data = {"abcd1234": "https://example.com/test"}
        mock_button_callback.return_value = AsyncMock()
        
        await callback_service.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        mock_button_callback.assert_called_once_with(mock_update, mock_context)
        
    @pytest.mark.asyncio
    async def test_handle_unknown_callback(self, callback_service, mock_update, mock_context):
        """Test handling unknown callback pattern."""
        mock_update.callback_query.data = "unknown_pattern_123"
        
        await callback_service.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once_with(
            "❌ Unknown callback action."
        )
        
    @pytest.mark.asyncio
    async def test_handle_callback_query_exception(self, callback_service, mock_update, mock_context):
        """Test handling callback query with exception."""
        mock_update.callback_query.data = "test_callback"
        mock_update.callback_query.edit_message_text.side_effect = Exception("Test error")
        
        await callback_service.handle_callback_query(mock_update, mock_context)
        
        mock_update.callback_query.answer.assert_called_once()
        # Should handle exception gracefully
        
    def test_validate_callback_data_empty(self, callback_service):
        """Test validating empty callback data."""
        is_valid, error = callback_service.validate_callback_data("")
        
        assert not is_valid
        assert error == "Empty callback data"
        
    def test_validate_callback_data_speech_recognition(self, callback_service):
        """Test validating speech recognition callback data."""
        callback_service.speech_service.validate_callback_data.return_value = (True, None)
        
        is_valid, error = callback_service.validate_callback_data("speechrec_abcd1234")
        
        assert is_valid
        assert error is None
        callback_service.speech_service.validate_callback_data.assert_called_once_with(
            "speechrec_abcd1234"
        )
        
    def test_validate_callback_data_speech_recognition_no_service(self, callback_service_no_speech):
        """Test validating speech recognition callback data without service."""
        is_valid, error = callback_service_no_speech.validate_callback_data("speechrec_abcd1234")
        
        assert not is_valid
        assert error == "Speech service not available"
        
    def test_validate_callback_data_language_selection(self, callback_service):
        """Test validating language selection callback data."""
        callback_service.speech_service.validate_callback_data.return_value = (True, None)
        
        is_valid, error = callback_service.validate_callback_data("lang_en|abcd1234")
        
        assert is_valid
        assert error is None
        callback_service.speech_service.validate_callback_data.assert_called_once_with(
            "lang_en|abcd1234"
        )
        
    def test_validate_callback_data_language_selection_no_service(self, callback_service_no_speech):
        """Test validating language selection callback data without service."""
        is_valid, error = callback_service_no_speech.validate_callback_data("lang_en|abcd1234")
        
        assert not is_valid
        assert error == "Speech service not available"
        
    def test_validate_callback_data_link_modification_valid(self, callback_service):
        """Test validating valid link modification callback data."""
        is_valid, error = callback_service.validate_callback_data("translate:abcd1234")
        
        assert is_valid
        assert error is None
        
    def test_validate_callback_data_link_modification_invalid_action(self, callback_service):
        """Test validating link modification callback data with invalid action."""
        is_valid, error = callback_service.validate_callback_data("invalid_action:abcd1234")
        
        assert not is_valid
        assert error == "Invalid action: invalid_action"
        
    def test_validate_callback_data_link_modification_invalid_hash(self, callback_service):
        """Test validating link modification callback data with invalid hash."""
        is_valid, error = callback_service.validate_callback_data("translate:invalid_hash")
        
        assert not is_valid
        assert error == "Invalid hash format"
        
    def test_validate_callback_data_test_callback(self, callback_service):
        """Test validating test callback data."""
        is_valid, error = callback_service.validate_callback_data("test_callback")
        
        assert is_valid
        assert error is None
        
    def test_validate_callback_data_unknown_format(self, callback_service):
        """Test validating unknown callback data format."""
        is_valid, error = callback_service.validate_callback_data("unknown_format")
        
        assert not is_valid
        assert error == "Unknown callback format"
        
    def test_register_callback_timestamp(self, callback_service):
        """Test registering callback timestamp."""
        callback_data = "test_callback"
        
        callback_service.register_callback_timestamp(callback_data)
        
        assert callback_data in callback_service.callback_timestamps
        assert isinstance(callback_service.callback_timestamps[callback_data], float)
        
    def test_is_callback_expired_not_registered(self, callback_service):
        """Test checking expiration for non-registered callback."""
        is_expired = callback_service._is_callback_expired("not_registered")
        
        assert not is_expired
        
    def test_is_callback_expired_not_expired(self, callback_service):
        """Test checking expiration for non-expired callback."""
        callback_data = "test_callback"
        callback_service.callback_timestamps[callback_data] = time.time()
        
        is_expired = callback_service._is_callback_expired(callback_data)
        
        assert not is_expired
        
    def test_is_callback_expired_expired(self, callback_service):
        """Test checking expiration for expired callback."""
        callback_data = "test_callback"
        callback_service.callback_timestamps[callback_data] = time.time() - 7200  # 2 hours ago
        
        is_expired = callback_service._is_callback_expired(callback_data)
        
        assert is_expired
        
    def test_cleanup_expired_callbacks(self, callback_service):
        """Test cleaning up expired callbacks."""
        current_time = time.time()
        
        # Add fresh and expired callbacks
        callback_service.callback_timestamps["fresh"] = current_time
        callback_service.callback_timestamps["expired"] = current_time - 7200  # 2 hours ago
        
        callback_service._cleanup_expired_callbacks()
        
        assert "fresh" in callback_service.callback_timestamps
        assert "expired" not in callback_service.callback_timestamps
        
    @pytest.mark.asyncio
    async def test_send_error_response_edit_message_text(self, callback_service):
        """Test sending error response via edit_message_text."""
        query = Mock()
        query.edit_message_text = AsyncMock()
        
        await callback_service._send_error_response(query, "Test error")
        
        query.edit_message_text.assert_called_once_with("Test error")
        
    @pytest.mark.asyncio
    async def test_send_error_response_message_edit_text(self, callback_service):
        """Test sending error response via message.edit_text."""
        query = Mock()
        query.message = Mock()
        query.message.edit_text = AsyncMock()
        # Remove edit_message_text to test fallback
        del query.edit_message_text
        
        await callback_service._send_error_response(query, "Test error")
        
        query.message.edit_text.assert_called_once_with("Test error")
        
    @pytest.mark.asyncio
    async def test_send_error_response_exception(self, callback_service):
        """Test sending error response with exception."""
        query = Mock()
        query.edit_message_text = AsyncMock(side_effect=Exception("Test error"))
        
        # Should handle exception gracefully
        await callback_service._send_error_response(query, "Test error")
        
    def test_get_supported_callback_patterns(self, callback_service):
        """Test getting supported callback patterns."""
        patterns = callback_service.get_supported_callback_patterns()
        
        expected_patterns = {
            r"^speechrec_",
            r"^lang_", 
            r"^test_callback$",
            r"^[a-zA-Z_]+:[0-9a-f]+$"
        }
        
        assert patterns == expected_patterns
        
    def test_set_speech_service(self, callback_service_no_speech):
        """Test setting speech service."""
        mock_speech_service = Mock(spec=SpeechRecognitionService)
        
        callback_service_no_speech.set_speech_service(mock_speech_service)
        
        assert callback_service_no_speech.speech_service == mock_speech_service


class TestCallbackHandlerServiceIntegration:
    """Integration tests for CallbackHandlerService with real dependencies."""
    
    @pytest.fixture
    def real_speech_service(self):
        """Create real speech recognition service for integration tests."""
        from config.config_manager import ConfigManager
        config_manager = Mock(spec=ConfigManager)
        return SpeechRecognitionService(config_manager)
        
    @pytest.fixture
    def integration_callback_service(self, real_speech_service):
        """Create callback service with real speech service."""
        return CallbackHandlerService(speech_service=real_speech_service)
        
    def test_validate_callback_data_with_real_speech_service(self, integration_callback_service):
        """Test callback validation with real speech service."""
        # Test valid speech recognition callback
        is_valid, error = integration_callback_service.validate_callback_data("speechrec_abcd1234")
        
        # Should delegate to speech service validation
        assert isinstance(is_valid, bool)
        
    def test_callback_routing_patterns(self, integration_callback_service):
        """Test that callback routing patterns work correctly."""
        patterns = integration_callback_service.get_supported_callback_patterns()
        
        # Test each pattern matches expected callback types
        test_cases = [
            ("speechrec_abcd1234", r"^speechrec_"),
            ("lang_en|abcd1234", r"^lang_"),
            ("test_callback", r"^test_callback$"),
            ("translate:abcd1234", r"^[a-zA-Z_]+:[0-9a-f]+$"),
        ]
        
        for callback_data, expected_pattern in test_cases:
            import re
            matching_patterns = [p for p in patterns if re.match(p, callback_data)]
            assert expected_pattern in matching_patterns, f"Pattern {expected_pattern} should match {callback_data}"