"""
Integration tests for MessageHandlerService with existing system components.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Any

from telegram import Update, Message, User, Chat
from telegram.ext import CallbackContext

from config.config_manager import ConfigManager
from modules.message_handler_service import MessageHandlerService
from modules.application_models import MessageContext


class TestMessageHandlerServiceIntegration:
    """Integration tests for MessageHandlerService."""
    
    @pytest.fixture
    def config_manager(self):
        """Create a real ConfigManager instance for integration testing."""
        return ConfigManager()
    
    @pytest.fixture
    def message_service(self, config_manager):
        """Create MessageHandlerService with real ConfigManager."""
        return MessageHandlerService(config_manager)
    
    @pytest.fixture
    def mock_update(self):
        """Create a realistic mock Update object."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.text = "Hello, this is a test message"
        update.message.from_user = Mock(spec=User)
        update.message.from_user.id = 12345
        update.message.from_user.username = "testuser"
        update.message.from_user.is_bot = False
        update.message.date = Mock()
        update.message.reply_text = AsyncMock()
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 67890
        update.effective_chat.type = "private"
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a realistic mock CallbackContext."""
        context = Mock(spec=CallbackContext)
        context.bot = Mock()
        context.bot.username = "testbot"
        return context
    
    @pytest.mark.asyncio
    async def test_service_initialization_with_real_config(self, message_service):
        """Test service initialization with real ConfigManager."""
        await message_service.initialize()
        
        assert message_service._initialized is True
        assert len(message_service.handlers) == 3
        
        # Verify handler types
        handler_names = [h.metadata.name for h in message_service.handlers]
        assert "text_message_handler" in handler_names
        assert "sticker_handler" in handler_names
        assert "location_handler" in handler_names
    
    @pytest.mark.asyncio
    async def test_message_context_creation_integration(self, mock_update, mock_context):
        """Test MessageContext creation with realistic data."""
        message_context = MessageContext.from_update(mock_update, mock_context)
        
        assert message_context.user_id == 12345
        assert message_context.chat_id == 67890
        assert message_context.chat_type == "private"
        assert message_context.message_text == "Hello, this is a test message"
        assert message_context.is_command is False
    
    @pytest.mark.asyncio
    @patch('modules.message_handler_service.update_message_history')
    @patch('modules.message_handler_service.should_restrict_user')
    @patch('modules.message_handler_service.process_message_content')
    @patch('modules.message_handler_service.needs_gpt_response')
    @patch('modules.message_handler_service.chat_history_manager')
    async def test_text_message_processing_flow(
        self, mock_chat_history, mock_needs_gpt, mock_process_content,
        mock_should_restrict, mock_update_history, message_service, mock_update, mock_context
    ):
        """Test complete text message processing flow."""
        # Setup mocks
        mock_should_restrict.return_value = False
        mock_process_content.return_value = ("cleaned text", [])
        mock_needs_gpt.return_value = (False, "")
        mock_chat_history.add_message = Mock()
        
        # Execute
        await message_service.handle_text_message(mock_update, mock_context)
        
        # Verify the flow
        mock_update_history.assert_called_once_with(12345, "Hello, this is a test message")
        mock_should_restrict.assert_called_once_with("Hello, this is a test message")
        mock_process_content.assert_called_once_with("Hello, this is a test message")
        mock_needs_gpt.assert_called_once()
        mock_chat_history.add_message.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('modules.message_handler_service.extract_urls')
    async def test_url_extraction_integration(
        self, mock_extract_urls, message_service, mock_update, mock_context
    ):
        """Test URL extraction integration."""
        mock_extract_urls.return_value = ["http://example.com", "http://test.com"]
        mock_update.message.text = "Check out http://example.com and http://test.com"
        
        await message_service.handle_text_message(mock_update, mock_context)
        
        # Verify URL extraction was called
        mock_extract_urls.assert_called_with("Check out http://example.com and http://test.com")
    
    @pytest.mark.asyncio
    async def test_handler_priority_ordering(self, message_service):
        """Test that handlers are ordered by priority correctly."""
        await message_service.initialize()
        
        # Check that handlers are sorted by priority (descending)
        priorities = [h.metadata.priority for h in message_service.handlers]
        assert priorities == sorted(priorities, reverse=True)
        
        # Text handler should have highest priority
        assert message_service.handlers[0].metadata.name == "text_message_handler"
        assert message_service.handlers[0].metadata.priority == 10
    
    @pytest.mark.asyncio
    async def test_error_resilience(self, message_service, mock_context):
        """Test that service handles errors gracefully."""
        # Create an update that will cause MessageContext.from_update to fail
        bad_update = Mock(spec=Update)
        bad_update.effective_user = None  # This will cause ValueError
        bad_update.effective_chat = None
        
        # Should not raise exception
        await message_service.handle_text_message(bad_update, mock_context)
        
        # Service should still be initialized
        assert message_service._initialized is True
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self, message_service):
        """Test complete service lifecycle."""
        # Initially not initialized
        assert message_service._initialized is False
        assert len(message_service.handlers) == 0
        
        # Initialize
        await message_service.initialize()
        assert message_service._initialized is True
        assert len(message_service.handlers) > 0
        
        # Get metadata
        metadata = message_service.get_handler_metadata()
        assert len(metadata) == len(message_service.handlers)
        
        # Shutdown
        await message_service.shutdown()
        assert message_service._initialized is False
        assert len(message_service.handlers) == 0
    
    @pytest.mark.asyncio
    @patch('modules.message_handler_service.gpt_response')
    @patch('modules.message_handler_service.needs_gpt_response')
    @patch('modules.message_handler_service.process_message_content')
    @patch('modules.message_handler_service.should_restrict_user')
    async def test_gpt_response_integration(
        self, mock_should_restrict, mock_process_content, mock_needs_gpt,
        mock_gpt_response, message_service, mock_update, mock_context
    ):
        """Test GPT response integration."""
        # Setup for GPT response
        mock_should_restrict.return_value = False
        mock_process_content.return_value = ("cleaned text", [])
        mock_needs_gpt.return_value = (True, "private")
        
        # Execute
        await message_service.handle_text_message(mock_update, mock_context)
        
        # Verify GPT response was called
        mock_gpt_response.assert_called_once_with(
            mock_update, mock_context, response_type="private", message_text_override="cleaned text"
        )
    
    @pytest.mark.asyncio
    async def test_multiple_message_types(self, message_service, mock_context):
        """Test handling different message types."""
        await message_service.initialize()
        
        # Test text message
        text_update = Mock(spec=Update)
        text_update.message = Mock(spec=Message)
        text_update.message.text = "Hello"
        text_update.effective_chat = Mock(spec=Chat)
        text_update.effective_user = Mock(spec=User)
        
        await message_service.handle_text_message(text_update, mock_context)
        
        # Test sticker message
        sticker_update = Mock(spec=Update)
        sticker_update.message = Mock(spec=Message)
        sticker_update.message.sticker = Mock()
        sticker_update.effective_chat = Mock(spec=Chat)
        sticker_update.effective_user = Mock(spec=User)
        
        await message_service.handle_sticker_message(sticker_update, mock_context)
        
        # Test location message
        location_update = Mock(spec=Update)
        location_update.message = Mock(spec=Message)
        location_update.message.location = Mock()
        location_update.effective_chat = Mock(spec=Chat)
        location_update.effective_user = Mock(spec=User)
        
        await message_service.handle_location_message(location_update, mock_context)
        
        # All should complete without errors
    
    @pytest.mark.asyncio
    async def test_config_manager_integration(self, message_service):
        """Test integration with ConfigManager."""
        await message_service.initialize()
        
        # Get text handler
        text_handler = next(
            (h for h in message_service.handlers if h.metadata.name == "text_message_handler"),
            None
        )
        
        assert text_handler is not None
        assert hasattr(text_handler, 'config_manager')
        assert isinstance(text_handler.config_manager, ConfigManager)


if __name__ == "__main__":
    pytest.main([__file__])