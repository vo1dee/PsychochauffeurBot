"""
Unit tests for MessageHandlerService and related components.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any, Dict, List

from telegram import Update, Message, User, Chat, Sticker, Location
from telegram.ext import CallbackContext

from config.config_manager import ConfigManager
from modules.application_models import MessageContext, HandlerMetadata
from modules.message_handler_service import (
    MessageHandlerService, BaseMessageHandler, TextMessageHandler,
    StickerHandler, LocationHandler
)
from modules.utils import MessageCounter


class TestBaseMessageHandler:
    """Test cases for BaseMessageHandler abstract base class."""
    
    def test_base_handler_initialization(self):
        """Test BaseMessageHandler initialization with metadata."""
        
        class TestHandler(BaseMessageHandler):
            async def can_handle(self, message_context: MessageContext) -> bool:
                return True
            
            async def handle(self, message_context: MessageContext) -> None:
                pass
        
        handler = TestHandler(
            name="test_handler",
            description="Test handler description",
            message_types=["text", "sticker"],
            priority=5
        )
        
        assert handler.metadata.name == "test_handler"
        assert handler.metadata.description == "Test handler description"
        assert handler.metadata.message_types == ["text", "sticker"]
        assert handler.metadata.priority == 5
        assert handler.metadata.enabled is True


class TestTextMessageHandler:
    """Test cases for TextMessageHandler."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager for testing."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock()
        return config_manager
    
    @pytest.fixture
    def mock_message_counter(self):
        """Mock MessageCounter for testing."""
        return Mock(spec=MessageCounter)
    
    @pytest.fixture
    def text_handler(self, mock_config_manager, mock_message_counter):
        """Create TextMessageHandler instance for testing."""
        return TextMessageHandler(mock_config_manager, mock_message_counter)
    
    @pytest.fixture
    def mock_update(self):
        """Create mock Update object."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.text = "Test message"
        update.message.from_user = Mock(spec=User)
        update.message.from_user.id = 123
        update.message.from_user.username = "testuser"
        update.message.date = Mock()
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 456
        update.effective_chat.type = "private"
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create mock CallbackContext."""
        context = Mock(spec=CallbackContext)
        context.bot = Mock()
        context.bot.username = "testbot"
        return context
    
    @pytest.fixture
    def message_context(self, mock_update, mock_context):
        """Create MessageContext for testing."""
        return MessageContext.from_update(mock_update, mock_context)
    
    def test_handler_initialization(self, text_handler):
        """Test TextMessageHandler initialization."""
        assert text_handler.metadata.name == "text_message_handler"
        assert text_handler.metadata.description == "Handles text messages, URL processing, and GPT responses"
        assert text_handler.metadata.message_types == ["text"]
        assert text_handler.metadata.priority == 10
    
    @pytest.mark.asyncio
    async def test_can_handle_text_message(self, text_handler, message_context):
        """Test can_handle method for valid text messages."""
        result = await text_handler.can_handle(message_context)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_can_handle_command_message(self, text_handler, message_context):
        """Test can_handle method rejects command messages."""
        message_context.message_text = "/start"
        message_context.is_command = True
        
        result = await text_handler.can_handle(message_context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_can_handle_no_text(self, text_handler, message_context):
        """Test can_handle method rejects messages without text."""
        message_context.message_text = None
        
        result = await text_handler.can_handle(message_context)
        assert result is False
    
    @pytest.mark.asyncio
    @patch('modules.message_handler_service.update_message_history')
    @patch('modules.message_handler_service.should_restrict_user')
    @patch('modules.message_handler_service.process_message_content')
    @patch('modules.message_handler_service.needs_gpt_response')
    async def test_handle_basic_message(
        self, mock_needs_gpt, mock_process_content, mock_should_restrict, 
        mock_update_history, text_handler, message_context
    ):
        """Test basic message handling flow."""
        # Setup mocks
        mock_should_restrict.return_value = False
        mock_process_content.return_value = ("cleaned text", [])
        mock_needs_gpt.return_value = (False, "")
        
        # Execute
        await text_handler.handle(message_context)
        
        # Verify
        mock_update_history.assert_called_once_with(123, "Test message")
        mock_should_restrict.assert_called_once_with("Test message")
        mock_process_content.assert_called_once_with("Test message")
        mock_needs_gpt.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('modules.message_handler_service.restrict_user')
    @patch('modules.message_handler_service.should_restrict_user')
    async def test_handle_restricted_user(
        self, mock_should_restrict, mock_restrict_user, text_handler, message_context
    ):
        """Test handling of restricted users."""
        # Setup mocks
        mock_should_restrict.return_value = True
        
        # Execute
        await text_handler.handle(message_context)
        
        # Verify
        mock_restrict_user.assert_called_once_with(message_context.update, message_context.context)
    
    @pytest.mark.asyncio
    @patch('modules.message_handler_service.gpt_response')
    @patch('modules.message_handler_service.needs_gpt_response')
    @patch('modules.message_handler_service.process_message_content')
    @patch('modules.message_handler_service.should_restrict_user')
    async def test_handle_gpt_response_needed(
        self, mock_should_restrict, mock_process_content, mock_needs_gpt, 
        mock_gpt_response, text_handler, message_context
    ):
        """Test handling when GPT response is needed."""
        # Setup mocks
        mock_should_restrict.return_value = False
        mock_process_content.return_value = ("cleaned text", [])
        mock_needs_gpt.return_value = (True, "mention")
        
        # Execute
        await text_handler.handle(message_context)
        
        # Verify
        mock_gpt_response.assert_called_once_with(
            message_context.update, 
            message_context.context, 
            response_type="mention", 
            message_text_override="cleaned text"
        )
    
    @pytest.mark.asyncio
    async def test_handle_translation_command(self, text_handler, mock_update, mock_context):
        """Test БЛЯ! translation command handling."""
        # Setup
        mock_update.message.text = "бля!"
        message_context = MessageContext.from_update(mock_update, mock_context)
        message_context.message_text = "бля!"
        
        with patch('modules.message_handler_service.get_previous_message') as mock_get_prev, \
             patch('modules.keyboard_translator.auto_translate_text') as mock_translate:
            
            mock_get_prev.return_value = "previous message"
            mock_translate.return_value = "translated text"
            mock_update.message.reply_text = AsyncMock()
            
            # Execute
            await text_handler.handle(message_context)
            
            # Verify
            mock_get_prev.assert_called_once_with(123)
            mock_translate.assert_called_once_with("previous message")
            mock_update.message.reply_text.assert_called_once_with("@testuser хотів сказати: translated text")
    
    @pytest.mark.asyncio
    async def test_should_trigger_random_gpt_private_chat(self, text_handler, mock_update, mock_context):
        """Test random GPT trigger logic for private chats."""
        mock_update.effective_chat.type = "private"
        
        result = await text_handler._should_trigger_random_gpt(mock_update, "test message", "test message")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_should_trigger_random_gpt_with_urls(self, text_handler, mock_update, mock_context):
        """Test random GPT trigger logic with URLs in message."""
        mock_update.effective_chat.type = "group"
        
        with patch('modules.message_handler_service.extract_urls') as mock_extract:
            mock_extract.return_value = ["http://example.com"]
            
            result = await text_handler._should_trigger_random_gpt(mock_update, "test http://example.com", "test")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_should_trigger_random_gpt_disabled_config(self, text_handler, mock_update, mock_context):
        """Test random GPT trigger when disabled in config."""
        mock_update.effective_chat.type = "group"
        text_handler.config_manager.get_config.return_value = {"enabled": False}
        
        with patch('modules.message_handler_service.extract_urls') as mock_extract:
            mock_extract.return_value = []
            
            result = await text_handler._should_trigger_random_gpt(mock_update, "test message", "test message")
            
            assert result is False


class TestStickerHandler:
    """Test cases for StickerHandler."""
    
    @pytest.fixture
    def sticker_handler(self):
        """Create StickerHandler instance for testing."""
        return StickerHandler()
    
    @pytest.fixture
    def mock_update_with_sticker(self):
        """Create mock Update with sticker."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.sticker = Mock(spec=Sticker)
        update.message.sticker.file_id = "test_file_id"
        update.message.sticker.file_unique_id = "test_unique_id"
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 456
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create mock CallbackContext."""
        return Mock(spec=CallbackContext)
    
    def test_handler_initialization(self, sticker_handler):
        """Test StickerHandler initialization."""
        assert sticker_handler.metadata.name == "sticker_handler"
        assert sticker_handler.metadata.description == "Handles sticker messages and restriction logic"
        assert sticker_handler.metadata.message_types == ["sticker"]
        assert sticker_handler.metadata.priority == 5
    
    @pytest.mark.asyncio
    async def test_can_handle_sticker_message(self, sticker_handler, mock_update_with_sticker, mock_context):
        """Test can_handle method for sticker messages."""
        message_context = MessageContext.from_update(mock_update_with_sticker, mock_context)
        
        result = await sticker_handler.can_handle(message_context)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_can_handle_non_sticker_message(self, sticker_handler, mock_context):
        """Test can_handle method for non-sticker messages."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.sticker = None
        update.effective_chat = Mock(spec=Chat)
        update.effective_user = Mock(spec=User)
        
        message_context = MessageContext.from_update(update, mock_context)
        
        result = await sticker_handler.can_handle(message_context)
        assert result is False
    
    @pytest.mark.asyncio
    @patch('modules.message_handler_service.handle_restriction_sticker')
    async def test_handle_restriction_sticker(
        self, mock_handle_restriction, sticker_handler, mock_update_with_sticker, mock_context
    ):
        """Test handling of restriction stickers."""
        # Setup restriction sticker
        mock_update_with_sticker.message.sticker.file_unique_id = "AgAD9hQAAtMUCVM"
        message_context = MessageContext.from_update(mock_update_with_sticker, mock_context)
        
        # Execute
        await sticker_handler.handle(message_context)
        
        # Verify
        mock_handle_restriction.assert_called_once_with(mock_update_with_sticker, mock_context)
    
    @pytest.mark.asyncio
    async def test_handle_regular_sticker(self, sticker_handler, mock_update_with_sticker, mock_context):
        """Test handling of regular (non-restriction) stickers."""
        message_context = MessageContext.from_update(mock_update_with_sticker, mock_context)
        
        # Execute (should not raise any exceptions)
        await sticker_handler.handle(message_context)


class TestLocationHandler:
    """Test cases for LocationHandler."""
    
    @pytest.fixture
    def location_handler(self):
        """Create LocationHandler instance for testing."""
        return LocationHandler()
    
    @pytest.fixture
    def mock_update_with_location(self):
        """Create mock Update with location."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.location = Mock(spec=Location)
        update.message.location.latitude = 50.4501
        update.message.location.longitude = 30.5234
        update.message.reply_sticker = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 456
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create mock CallbackContext."""
        return Mock(spec=CallbackContext)
    
    def test_handler_initialization(self, location_handler):
        """Test LocationHandler initialization."""
        assert location_handler.metadata.name == "location_handler"
        assert location_handler.metadata.description == "Handles location messages by replying with a sticker"
        assert location_handler.metadata.message_types == ["location"]
        assert location_handler.metadata.priority == 5
    
    @pytest.mark.asyncio
    async def test_can_handle_location_message(self, location_handler, mock_update_with_location, mock_context):
        """Test can_handle method for location messages."""
        message_context = MessageContext.from_update(mock_update_with_location, mock_context)
        
        result = await location_handler.can_handle(message_context)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_can_handle_non_location_message(self, location_handler, mock_context):
        """Test can_handle method for non-location messages."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.location = None
        update.effective_chat = Mock(spec=Chat)
        update.effective_user = Mock(spec=User)
        
        message_context = MessageContext.from_update(update, mock_context)
        
        result = await location_handler.can_handle(message_context)
        assert result is False
    
    @pytest.mark.asyncio
    @patch('modules.message_handler_service.Stickers')
    async def test_handle_location_success(
        self, mock_stickers, location_handler, mock_update_with_location, mock_context
    ):
        """Test successful location handling."""
        mock_stickers.LOCATION = "location_sticker_id"
        message_context = MessageContext.from_update(mock_update_with_location, mock_context)
        
        # Execute
        await location_handler.handle(message_context)
        
        # Verify
        mock_update_with_location.message.reply_sticker.assert_called_once_with(sticker="location_sticker_id")
    
    @pytest.mark.asyncio
    @patch('modules.message_handler_service.Stickers')
    async def test_handle_location_fallback(
        self, mock_stickers, location_handler, mock_update_with_location, mock_context
    ):
        """Test location handling fallback when sticker fails."""
        mock_stickers.LOCATION = "location_sticker_id"
        mock_update_with_location.message.reply_sticker.side_effect = Exception("Sticker failed")
        message_context = MessageContext.from_update(mock_update_with_location, mock_context)
        
        # Execute
        await location_handler.handle(message_context)
        
        # Verify fallback
        mock_update_with_location.message.reply_text.assert_called_once_with("📍 Location received!")


class TestMessageHandlerService:
    """Test cases for MessageHandlerService."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager for testing."""
        return Mock(spec=ConfigManager)
    
    @pytest.fixture
    def message_service(self, mock_config_manager):
        """Create MessageHandlerService instance for testing."""
        return MessageHandlerService(mock_config_manager)
    
    @pytest.fixture
    def mock_update(self):
        """Create mock Update object."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.text = "Test message"
        update.message.from_user = Mock(spec=User)
        update.message.from_user.id = 123
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 456
        update.effective_chat.type = "private"
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create mock CallbackContext."""
        return Mock(spec=CallbackContext)
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, message_service):
        """Test MessageHandlerService initialization."""
        await message_service.initialize()
        
        assert message_service._initialized is True
        assert len(message_service.handlers) == 3
        
        # Check handlers are sorted by priority
        priorities = [h.metadata.priority for h in message_service.handlers]
        assert priorities == sorted(priorities, reverse=True)
    
    @pytest.mark.asyncio
    async def test_service_shutdown(self, message_service):
        """Test MessageHandlerService shutdown."""
        await message_service.initialize()
        await message_service.shutdown()
        
        assert message_service._initialized is False
        assert len(message_service.handlers) == 0
    
    @pytest.mark.asyncio
    @patch('modules.message_handler_service.extract_urls')
    async def test_handle_text_message(self, mock_extract_urls, message_service, mock_update, mock_context):
        """Test text message handling."""
        mock_extract_urls.return_value = []
        
        with patch.object(message_service.handlers[0] if message_service.handlers else Mock(), 'handle', new_callable=AsyncMock) as mock_handle:
            await message_service.handle_text_message(mock_update, mock_context)
            
            # Service should be initialized automatically
            assert message_service._initialized is True
    
    @pytest.mark.asyncio
    async def test_handle_sticker_message(self, message_service, mock_context):
        """Test sticker message handling."""
        # Create sticker update
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.sticker = Mock(spec=Sticker)
        update.effective_chat = Mock(spec=Chat)
        update.effective_user = Mock(spec=User)
        
        await message_service.handle_sticker_message(update, mock_context)
        
        # Service should be initialized automatically
        assert message_service._initialized is True
    
    @pytest.mark.asyncio
    async def test_handle_location_message(self, message_service, mock_context):
        """Test location message handling."""
        # Create location update
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.location = Mock(spec=Location)
        update.effective_chat = Mock(spec=Chat)
        update.effective_user = Mock(spec=User)
        
        await message_service.handle_location_message(update, mock_context)
        
        # Service should be initialized automatically
        assert message_service._initialized is True
    
    @pytest.mark.asyncio
    async def test_process_urls(self, message_service, mock_update, mock_context):
        """Test URL processing."""
        urls = ["http://example.com", "http://test.com"]
        
        await message_service.process_urls(mock_update, mock_context, urls)
        
        # Should not raise any exceptions
    
    @pytest.mark.asyncio
    async def test_check_random_gpt_response(self, message_service, mock_update, mock_context):
        """Test random GPT response checking."""
        result = await message_service.check_random_gpt_response(mock_update, mock_context)
        
        # Should return a boolean
        assert isinstance(result, bool)
    
    def test_get_handler_metadata(self, message_service):
        """Test getting handler metadata."""
        # Initialize with some handlers
        message_service.handlers = [
            Mock(metadata=HandlerMetadata("test1", "desc1", ["text"])),
            Mock(metadata=HandlerMetadata("test2", "desc2", ["sticker"]))
        ]
        
        metadata = message_service.get_handler_metadata()
        
        assert len(metadata) == 2
        assert all(isinstance(m, HandlerMetadata) for m in metadata)
        assert metadata[0].name == "test1"
        assert metadata[1].name == "test2"
    
    @pytest.mark.asyncio
    async def test_error_handling_in_text_message(self, message_service, mock_update, mock_context):
        """Test error handling in text message processing."""
        # Make MessageContext.from_update raise an exception
        with patch('modules.message_handler_service.MessageContext.from_update') as mock_from_update:
            mock_from_update.side_effect = Exception("Test error")
            
            # Should not raise exception, but log error
            await message_service.handle_text_message(mock_update, mock_context)
    
    @pytest.mark.asyncio
    async def test_auto_initialization(self, message_service, mock_update, mock_context):
        """Test that service auto-initializes when needed."""
        assert message_service._initialized is False
        
        await message_service.handle_text_message(mock_update, mock_context)
        
        assert message_service._initialized is True
        assert len(message_service.handlers) > 0


if __name__ == "__main__":
    pytest.main([__file__])