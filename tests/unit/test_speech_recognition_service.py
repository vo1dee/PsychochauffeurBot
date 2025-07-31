"""
Unit tests for SpeechRecognitionService.

This module contains comprehensive unit tests for the SpeechRecognitionService,
covering all functionality including voice/video note handling, language selection,
callback processing, and configuration management.
"""

import pytest
import hashlib
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, Message, Voice, VideoNote, CallbackQuery, Chat, User, Bot
from telegram.ext import CallbackContext

from modules.speech_recognition_service import SpeechRecognitionService
from modules.speechmatics import (
    SpeechmaticsLanguageNotExpected, 
    SpeechmaticsNoSpeechDetected,
    SpeechmaticsRussianDetected
)
from config.config_manager import ConfigManager


@pytest.fixture
def mock_config_manager():
    """Create a mock ConfigManager."""
    config_manager = Mock(spec=ConfigManager)
    config_manager.get_config = AsyncMock()
    config_manager.save_config = AsyncMock()
    return config_manager


@pytest.fixture
def speech_service(mock_config_manager):
    """Create a SpeechRecognitionService instance with mocked dependencies."""
    return SpeechRecognitionService(config_manager=mock_config_manager)


@pytest.fixture
def mock_update():
    """Create a mock Telegram Update."""
    update = Mock(spec=Update)
    update.effective_chat = Mock(spec=Chat)
    update.effective_chat.id = 12345
    update.effective_chat.type = "group"
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 67890
    update.message = Mock(spec=Message)
    return update


@pytest.fixture
def mock_context():
    """Create a mock CallbackContext."""
    context = Mock(spec=CallbackContext)
    context.bot = Mock(spec=Bot)
    return context


@pytest.fixture
def mock_voice_update(mock_update):
    """Create a mock update with voice message."""
    mock_update.message.voice = Mock(spec=Voice)
    mock_update.message.voice.file_id = "voice_file_123"
    return mock_update


@pytest.fixture
def mock_video_note_update(mock_update):
    """Create a mock update with video note message."""
    mock_update.message.video_note = Mock(spec=VideoNote)
    mock_update.message.video_note.file_id = "video_note_456"
    return mock_update


@pytest.fixture
def mock_callback_update():
    """Create a mock update with callback query."""
    update = Mock(spec=Update)
    update.callback_query = Mock(spec=CallbackQuery)
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_chat = Mock(spec=Chat)
    update.effective_chat.id = 12345
    return update


class TestSpeechRecognitionServiceInitialization:
    """Test service initialization and lifecycle."""
    
    def test_init(self, mock_config_manager):
        """Test service initialization."""
        service = SpeechRecognitionService(config_manager=mock_config_manager)
        
        assert service.config_manager is mock_config_manager
        assert isinstance(service.file_id_hash_map, dict)
        assert len(service.file_id_hash_map) == 0
        
    @pytest.mark.asyncio
    async def test_initialize(self, speech_service):
        """Test service initialization method."""
        await speech_service.initialize()
        # Should complete without error
        
    @pytest.mark.asyncio
    async def test_shutdown(self, speech_service):
        """Test service shutdown method."""
        # Add some data to hash map
        speech_service.file_id_hash_map["test"] = "value"
        
        await speech_service.shutdown()
        
        # Hash map should be cleared
        assert len(speech_service.file_id_hash_map) == 0


class TestVoiceMessageHandling:
    """Test voice message handling functionality."""
    
    @pytest.mark.asyncio
    async def test_handle_voice_message_success(self, speech_service, mock_voice_update, mock_context):
        """Test successful voice message handling."""
        # Mock speech enabled
        speech_service.is_speech_enabled = AsyncMock(return_value=True)
        speech_service._send_speech_recognition_button = AsyncMock()
        
        await speech_service.handle_voice_message(mock_voice_update, mock_context)
        
        speech_service._send_speech_recognition_button.assert_called_once_with(
            mock_voice_update, mock_context, "voice_file_123"
        )
        
    @pytest.mark.asyncio
    async def test_handle_voice_message_speech_disabled(self, speech_service, mock_voice_update, mock_context):
        """Test voice message handling when speech is disabled."""
        # Mock speech disabled
        speech_service._should_process_speech = AsyncMock(return_value=False)
        speech_service._send_speech_recognition_button = AsyncMock()
        
        await speech_service.handle_voice_message(mock_voice_update, mock_context)
        
        speech_service._send_speech_recognition_button.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_handle_voice_message_no_voice(self, speech_service, mock_update, mock_context):
        """Test voice message handling with no voice in message."""
        mock_update.message.voice = None
        speech_service._should_process_speech = AsyncMock(return_value=True)
        speech_service._send_speech_recognition_button = AsyncMock()
        
        await speech_service.handle_voice_message(mock_update, mock_context)
        
        speech_service._send_speech_recognition_button.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_handle_voice_message_no_message(self, speech_service, mock_context):
        """Test voice message handling with no message in update."""
        update = Mock(spec=Update)
        update.message = None
        speech_service._should_process_speech = AsyncMock(return_value=True)
        speech_service._send_speech_recognition_button = AsyncMock()
        
        await speech_service.handle_voice_message(update, mock_context)
        
        speech_service._send_speech_recognition_button.assert_not_called()


class TestVideoNoteHandling:
    """Test video note message handling functionality."""
    
    @pytest.mark.asyncio
    async def test_handle_video_note_success(self, speech_service, mock_video_note_update, mock_context):
        """Test successful video note handling."""
        speech_service._should_process_speech = AsyncMock(return_value=True)
        speech_service._send_speech_recognition_button = AsyncMock()
        
        await speech_service.handle_video_note(mock_video_note_update, mock_context)
        
        speech_service._send_speech_recognition_button.assert_called_once_with(
            mock_video_note_update, mock_context, "video_note_456"
        )
        
    @pytest.mark.asyncio
    async def test_handle_video_note_speech_disabled(self, speech_service, mock_video_note_update, mock_context):
        """Test video note handling when speech is disabled."""
        speech_service._should_process_speech = AsyncMock(return_value=False)
        speech_service._send_speech_recognition_button = AsyncMock()
        
        await speech_service.handle_video_note(mock_video_note_update, mock_context)
        
        speech_service._send_speech_recognition_button.assert_not_called()


class TestSpeechRecognitionProcessing:
    """Test speech recognition callback processing."""
    
    @pytest.mark.asyncio
    async def test_process_speech_recognition_success(self, speech_service, mock_callback_update, mock_context):
        """Test successful speech recognition processing."""
        # Setup callback data
        file_id = "test_file_123"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        speech_service.file_id_hash_map[file_hash] = file_id
        
        mock_callback_update.callback_query.data = f"speechrec_{file_hash}"
        
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            mock_transcribe.return_value = "Hello world"
            mock_context.bot.send_message = AsyncMock()
            
            await speech_service.process_speech_recognition(mock_callback_update, mock_context)
            
            mock_transcribe.assert_called_once_with(mock_context.bot, file_id, language="auto")
            mock_context.bot.send_message.assert_called_once_with(
                chat_id=12345,
                text="🗣️ Recognized speech:\nHello world"
            )
            
    @pytest.mark.asyncio
    async def test_process_speech_recognition_no_speech_detected(self, speech_service, mock_callback_update, mock_context):
        """Test speech recognition when no speech is detected."""
        file_id = "test_file_123"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        speech_service.file_id_hash_map[file_hash] = file_id
        
        mock_callback_update.callback_query.data = f"speechrec_{file_hash}"
        
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            mock_transcribe.side_effect = SpeechmaticsNoSpeechDetected()
            mock_context.bot.send_message = AsyncMock()
            
            await speech_service.process_speech_recognition(mock_callback_update, mock_context)
            
            mock_context.bot.send_message.assert_called_once_with(
                chat_id=12345,
                text="❌ No speech was detected in the audio. Please try again with a clearer voice message."
            )
            
    @pytest.mark.asyncio
    async def test_process_speech_recognition_language_not_expected(self, speech_service, mock_callback_update, mock_context):
        """Test speech recognition when language is not expected."""
        file_id = "test_file_123"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        speech_service.file_id_hash_map[file_hash] = file_id
        
        mock_callback_update.callback_query.data = f"speechrec_{file_hash}"
        
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            with patch('modules.speech_recognition_service.get_language_keyboard') as mock_keyboard:
                mock_transcribe.side_effect = SpeechmaticsLanguageNotExpected()
                mock_keyboard.return_value = Mock()
                mock_context.bot.send_message = AsyncMock()
                
                await speech_service.process_speech_recognition(mock_callback_update, mock_context)
                
                mock_context.bot.send_message.assert_called_once()
                args, kwargs = mock_context.bot.send_message.call_args
                assert "Couldn't recognize the language" in kwargs['text']
                
    @pytest.mark.asyncio
    async def test_process_speech_recognition_invalid_callback_data(self, speech_service, mock_callback_update, mock_context):
        """Test speech recognition with invalid callback data."""
        mock_callback_update.callback_query.data = "invalid_data"
        
        await speech_service.process_speech_recognition(mock_callback_update, mock_context)
        
        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        args, kwargs = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Invalid callback data format" in args[0]
        
    @pytest.mark.asyncio
    async def test_process_speech_recognition_expired_hash(self, speech_service, mock_callback_update, mock_context):
        """Test speech recognition with expired file hash."""
        mock_callback_update.callback_query.data = "speechrec_expired_hash"
        
        await speech_service.process_speech_recognition(mock_callback_update, mock_context)
        
        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        args, kwargs = mock_callback_update.callback_query.edit_message_text.call_args
        assert "expired or is invalid" in args[0]


class TestLanguageSelection:
    """Test language selection callback handling."""
    
    @pytest.mark.asyncio
    async def test_handle_language_selection_success(self, speech_service, mock_callback_update, mock_context):
        """Test successful language selection."""
        file_id = "test_file_123"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        speech_service.file_id_hash_map[file_hash] = file_id
        
        mock_callback_update.callback_query.data = f"lang_en|{file_hash}"
        
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            mock_transcribe.return_value = "Hello world"
            
            await speech_service.handle_language_selection(mock_callback_update, mock_context)
            
            mock_transcribe.assert_called_once_with(mock_context.bot, file_id, language="en")
            mock_callback_update.callback_query.edit_message_text.assert_called_with(
                "🗣️ Recognized (en):\nHello world"
            )
            
    @pytest.mark.asyncio
    async def test_handle_language_selection_test_callback(self, speech_service, mock_callback_update, mock_context):
        """Test handling of test callback."""
        mock_callback_update.callback_query.data = "test_callback"
        
        await speech_service.handle_language_selection(mock_callback_update, mock_context)
        
        mock_callback_update.callback_query.edit_message_text.assert_called_once_with(
            "✅ Test callback received and handled!"
        )
        
    @pytest.mark.asyncio
    async def test_handle_language_selection_invalid_format(self, speech_service, mock_callback_update, mock_context):
        """Test language selection with invalid callback data format."""
        mock_callback_update.callback_query.data = "invalid_format"
        
        await speech_service.handle_language_selection(mock_callback_update, mock_context)
        
        mock_callback_update.callback_query.edit_message_text.assert_called_once_with(
            "❌ Invalid callback data. Please try again."
        )
        
    @pytest.mark.asyncio
    async def test_handle_language_selection_expired_hash(self, speech_service, mock_callback_update, mock_context):
        """Test language selection with expired file hash."""
        mock_callback_update.callback_query.data = "lang_en|expired_hash"
        
        await speech_service.handle_language_selection(mock_callback_update, mock_context)
        
        mock_callback_update.callback_query.edit_message_text.assert_called_once_with(
            "❌ This button has expired or is invalid. Please try again."
        )


class TestConfigurationManagement:
    """Test speech configuration management."""
    
    @pytest.mark.asyncio
    async def test_get_speech_config_exists(self, speech_service, mock_config_manager):
        """Test getting existing speech configuration."""
        mock_config = {
            "config_modules": {
                "speechmatics": {
                    "enabled": True,
                    "overrides": {}
                }
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        result = await speech_service.get_speech_config("12345", "group")
        
        assert result == {"enabled": True, "overrides": {}}
        mock_config_manager.get_config.assert_called_once_with(
            chat_id="12345", chat_type="group", module_name="speechmatics"
        )
        
    @pytest.mark.asyncio
    async def test_get_speech_config_not_exists(self, speech_service, mock_config_manager):
        """Test getting non-existent speech configuration."""
        mock_config_manager.get_config.return_value = None
        
        result = await speech_service.get_speech_config("12345", "group")
        
        assert result is None
        
    @pytest.mark.asyncio
    async def test_is_speech_enabled_true(self, speech_service):
        """Test checking if speech is enabled when it is."""
        speech_service.get_speech_config = AsyncMock(return_value={"enabled": True})
        
        result = await speech_service.is_speech_enabled("12345", "group")
        
        assert result is True
        
    @pytest.mark.asyncio
    async def test_is_speech_enabled_false(self, speech_service):
        """Test checking if speech is enabled when it's not."""
        speech_service.get_speech_config = AsyncMock(return_value={"enabled": False})
        
        result = await speech_service.is_speech_enabled("12345", "group")
        
        assert result is False
        
    @pytest.mark.asyncio
    async def test_is_speech_enabled_no_config(self, speech_service):
        """Test checking if speech is enabled when no config exists."""
        speech_service.get_speech_config = AsyncMock(return_value=None)
        
        result = await speech_service.is_speech_enabled("12345", "group")
        
        assert result is False
        
    @pytest.mark.asyncio
    async def test_toggle_speech_recognition_enable(self, speech_service, mock_config_manager):
        """Test enabling speech recognition."""
        speech_service.get_speech_config = AsyncMock(return_value={"enabled": False})
        
        await speech_service.toggle_speech_recognition("12345", "group", True)
        
        mock_config_manager.save_config.assert_called_once_with(
            chat_id="12345",
            chat_type="group", 
            module_name="speechmatics",
            enabled=True,
            overrides={}
        )
        
    @pytest.mark.asyncio
    async def test_toggle_speech_recognition_new_config(self, speech_service, mock_config_manager):
        """Test enabling speech recognition with new config."""
        speech_service.get_speech_config = AsyncMock(return_value=None)
        
        await speech_service.toggle_speech_recognition("12345", "group", True)
        
        mock_config_manager.save_config.assert_called_once_with(
            chat_id="12345",
            chat_type="group",
            module_name="speechmatics", 
            enabled=True,
            overrides={}
        )


class TestCallbackDataValidation:
    """Test callback data validation functionality."""
    
    def test_validate_callback_data_speechrec_valid(self, speech_service):
        """Test validation of valid speechrec callback data."""
        file_hash = "test_hash_123"
        speech_service.file_id_hash_map[file_hash] = "file_id"
        
        is_valid, error = speech_service.validate_callback_data(f"speechrec_{file_hash}")
        
        assert is_valid is True
        assert error is None
        
    def test_validate_callback_data_speechrec_expired(self, speech_service):
        """Test validation of expired speechrec callback data."""
        is_valid, error = speech_service.validate_callback_data("speechrec_expired_hash")
        
        assert is_valid is False
        assert error == "Speech recognition button has expired"
        
    def test_validate_callback_data_language_valid(self, speech_service):
        """Test validation of valid language callback data."""
        file_hash = "test_hash_123"
        speech_service.file_id_hash_map[file_hash] = "file_id"
        
        is_valid, error = speech_service.validate_callback_data(f"lang_en|{file_hash}")
        
        assert is_valid is True
        assert error is None
        
    def test_validate_callback_data_language_expired(self, speech_service):
        """Test validation of expired language callback data."""
        is_valid, error = speech_service.validate_callback_data("lang_en|expired_hash")
        
        assert is_valid is False
        assert error == "Language selection button has expired"
        
    def test_validate_callback_data_invalid_format(self, speech_service):
        """Test validation of invalid callback data format."""
        is_valid, error = speech_service.validate_callback_data("invalid_format")
        
        assert is_valid is False
        assert error == "Invalid callback data format"


class TestPrivateMethods:
    """Test private helper methods."""
    
    @pytest.mark.asyncio
    async def test_should_process_speech_enabled(self, speech_service, mock_update):
        """Test _should_process_speech when speech is enabled."""
        speech_service.is_speech_enabled = AsyncMock(return_value=True)
        
        result = await speech_service._should_process_speech(mock_update)
        
        assert result is True
        speech_service.is_speech_enabled.assert_called_once_with("12345", "group")
        
    @pytest.mark.asyncio
    async def test_should_process_speech_disabled(self, speech_service, mock_update):
        """Test _should_process_speech when speech is disabled."""
        speech_service.is_speech_enabled = AsyncMock(return_value=False)
        
        result = await speech_service._should_process_speech(mock_update)
        
        assert result is False
        
    @pytest.mark.asyncio
    async def test_should_process_speech_no_chat(self, speech_service):
        """Test _should_process_speech when no effective chat."""
        update = Mock(spec=Update)
        update.effective_chat = None
        
        result = await speech_service._should_process_speech(update)
        
        assert result is False
        
    @pytest.mark.asyncio
    async def test_send_speech_recognition_button(self, speech_service, mock_update, mock_context):
        """Test _send_speech_recognition_button method."""
        file_id = "test_file_123"
        mock_update.message.reply_text = AsyncMock()
        
        await speech_service._send_speech_recognition_button(mock_update, mock_context, file_id)
        
        # Check that file hash was stored
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        assert speech_service.file_id_hash_map[file_hash] == file_id
        
        # Check that reply was sent
        mock_update.message.reply_text.assert_called_once()
        args, kwargs = mock_update.message.reply_text.call_args
        assert "Press the button to recognize speech" in args[0]
        assert kwargs['reply_markup'] is not None
        
    @pytest.mark.asyncio
    async def test_send_speech_recognition_button_no_message(self, speech_service, mock_context):
        """Test _send_speech_recognition_button with no message."""
        update = Mock(spec=Update)
        update.message = None
        
        await speech_service._send_speech_recognition_button(update, mock_context, "file_id")
        
        # Should not add to hash map
        assert len(speech_service.file_id_hash_map) == 0


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_process_speech_recognition_general_exception(self, speech_service, mock_callback_update, mock_context):
        """Test speech recognition with general exception."""
        file_id = "test_file_123"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        speech_service.file_id_hash_map[file_hash] = file_id
        
        mock_callback_update.callback_query.data = f"speechrec_{file_hash}"
        
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            mock_transcribe.side_effect = Exception("API Error")
            mock_context.bot.send_message = AsyncMock()
            
            await speech_service.process_speech_recognition(mock_callback_update, mock_context)
            
            mock_context.bot.send_message.assert_called_once_with(
                chat_id=12345,
                text="❌ Speech recognition failed: API Error"
            )
            
    @pytest.mark.asyncio
    async def test_handle_language_selection_general_exception(self, speech_service, mock_callback_update, mock_context):
        """Test language selection with general exception."""
        file_id = "test_file_123"
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        speech_service.file_id_hash_map[file_hash] = file_id
        
        mock_callback_update.callback_query.data = f"lang_en|{file_hash}"
        
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            mock_transcribe.side_effect = Exception("API Error")
            
            await speech_service.handle_language_selection(mock_callback_update, mock_context)
            
            mock_callback_update.callback_query.edit_message_text.assert_called_with(
                "❌ Speech recognition failed: API Error", reply_markup=None
            )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_process_speech_recognition_no_callback_query(self, speech_service, mock_context):
        """Test speech recognition processing with no callback query."""
        update = Mock(spec=Update)
        update.callback_query = None
        
        await speech_service.process_speech_recognition(update, mock_context)
        
        # Should return early without error
        
    @pytest.mark.asyncio
    async def test_process_speech_recognition_no_callback_data(self, speech_service, mock_callback_update, mock_context):
        """Test speech recognition processing with no callback data."""
        mock_callback_update.callback_query.data = None
        
        await speech_service.process_speech_recognition(mock_callback_update, mock_context)
        
        # Should return early without error
        
    @pytest.mark.asyncio
    async def test_handle_language_selection_no_effective_chat(self, speech_service, mock_context):
        """Test language selection with no effective chat."""
        update = Mock(spec=Update)
        update.callback_query = Mock(spec=CallbackQuery)
        update.callback_query.answer = AsyncMock()
        update.callback_query.data = "lang_en|hash123"
        update.effective_chat = None
        
        file_hash = "hash123"
        speech_service.file_id_hash_map[file_hash] = "file_id"
        
        with patch('modules.speech_recognition_service.transcribe_telegram_voice') as mock_transcribe:
            mock_transcribe.return_value = "Hello"
            
            await speech_service.handle_language_selection(update, mock_context)
            
            # Should complete without sending message to chat