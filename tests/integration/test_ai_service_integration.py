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
    def mock_update(self):
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
    def mock_context(self):
        """Create a mock callback context."""
        context = Mock(spec=CallbackContext)
        context.args = []
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_answer_from_gpt_basic(self):
        """Test basic GPT response generation."""
        with patch('modules.gpt.OpenAIAsyncClient') as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = "This is a test response"
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            result = await answer_from_gpt("Hello, how are you?")
            
            assert result == "This is a test response"
            mock_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verify_api_key(self):
        """Test API key verification."""
        with patch('modules.gpt.Config') as mock_config:
            mock_config.OPENAI_API_KEY = "test_key_123"
            
            result = await verify_api_key()
            
            assert result is True