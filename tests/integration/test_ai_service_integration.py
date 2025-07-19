"""
Integration tests for AI service integration and response handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, Chat, User
from telegram.ext import CallbackContext

from modules.gpt import (
    answer_from_gpt, gpt_response, analyze_image, 
    get_context_messages, verify_api_key, OpenAIAsyncClient,
    ask_gpt_command, handle_photo_analysis
)
from modules.error_handler import ErrorHandler


class TestGPTIntegration:
    """Integration tests for GPT functionality."""
    
    @pytest.fixture
    def mock_update(self) -> None:
        """Create a mock Telegram update."""
        user = User(id=123, first_name="Test", is_bot=False)
        chat = Chat(id=-1001234567890, type="supergroup")
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user,
            text="Test message"
        )
        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        return update
    
    @pytest.fixture
    def mock_context(self) -> None:
        """Create a mock callback context."""
        context = Mock(spec=CallbackContext)
        context.args = []
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_answer_from_gpt_basic(self) -> None:
        """Test basic GPT response generation."""
        # Create mock update and context
        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.text = "Hello, how are you?"
        mock_update.effective_chat = Mock()
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        
        with patch('modules.gpt.gpt_response') as mock_gpt_response:
            mock_gpt_response.return_value = "This is a test response"
            
            result = await answer_from_gpt(
                "Hello, how are you?", 
                update=mock_update, 
                context=mock_context, 
                return_text=True
            )
            
            assert result == "This is a test response"
            mock_gpt_response.assert_called_once_with(
                mock_update, 
                mock_context, 
                response_type="command", 
                return_text=True
            )
    
    @pytest.mark.asyncio
    async def test_verify_api_key(self) -> None:
        """Test API key verification."""
        with patch('modules.gpt.Config') as mock_config:
            mock_config.OPENAI_API_KEY = "test_key_123"
            
            result = await verify_api_key()
            
            assert result is True