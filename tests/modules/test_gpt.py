"""
Comprehensive tests for the GPT module focusing on API integration and response processing.
This module tests OpenAI API calls, response parsing, and prompt engineering functionality.
"""

import pytest
import asyncio
import json
import base64
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List, Optional

# Telegram imports
from telegram import Update, Message, User, Chat
from telegram.ext import CallbackContext

# Local imports
from modules import gpt
from modules.gpt import (
    OpenAIAsyncClient,
    gpt_response,
    analyze_image,
    get_system_prompt,
    get_context_messages,
    ask_gpt_command,
    answer_from_gpt,
    ensure_api_connectivity,
    optimize_image,
    verify_api_key,
    verify_connectivity,
    check_api_health
)
from tests.mocks.enhanced_mocks import EnhancedOpenAIMock, mock_registry
from tests.fixtures.shared_fixtures import (
    sample_user_data,
    sample_chat_data,
    sample_config_data,
    sample_api_response_data
)


class TestOpenAIAsyncClient:
    """Test the custom OpenAI async client implementation."""
    
    @pytest.fixture
    def client(self):
        """Create a test client instance."""
        return OpenAIAsyncClient(
            api_key="test-api-key",
            base_url="https://api.openai.com/v1"
        )
    
    def test_client_initialization(self, client):
        """Test client initialization with proper configuration."""
        assert client.api_key == "test-api-key"
        assert client.base_url == "https://api.openai.com/v1"
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == "Bearer test-api-key"
        assert client.headers["Content-Type"] == "application/json"
    
    def test_client_base_url_normalization(self):
        """Test that base URL is properly normalized."""
        client = OpenAIAsyncClient(
            api_key="test-key",
            base_url="https://api.openai.com/v1/"
        )
        assert client.base_url == "https://api.openai.com/v1"
    
    @pytest.mark.asyncio
    async def test_chat_completions_create_success(self, client):
        """Test successful chat completion creation."""
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "Test response",
                        "role": "assistant"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            },
            "model": "gpt-4o-mini"
        }
        
        with patch.object(client._client, 'post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            result = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Test message"}],
                max_tokens=100,
                temperature=0.7
            )
            
            assert result == mock_response_data
            mock_post.assert_called_once()
            
            # Verify the request payload
            call_args = mock_post.call_args
            assert call_args[1]["json"]["model"] == "gpt-4o-mini"
            assert call_args[1]["json"]["max_tokens"] == 100
            assert call_args[1]["json"]["temperature"] == 0.7
    
    @pytest.mark.asyncio
    async def test_chat_completions_create_http_error(self, client):
        """Test handling of HTTP errors in chat completion."""
        with patch.object(client._client, 'post') as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = Exception("HTTP 429: Rate limit exceeded")
            mock_post.return_value = mock_response
            
            with pytest.raises(Exception, match="HTTP 429: Rate limit exceeded"):
                await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "Test"}],
                    max_tokens=100,
                    temperature=0.7
                )


class TestGPTResponse:
    """Test the main GPT response generation functionality."""
    
    @pytest.fixture
    def mock_update(self, sample_user_data, sample_chat_data):
        """Create a mock Telegram update."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.text = "Test message"
        update.message.from_user = Mock(spec=User)
        update.message.from_user.id = sample_user_data["user_id"]
        update.message.from_user.username = sample_user_data["username"]
        update.message.date = datetime.now(timezone.utc)
        update.message.reply_text = AsyncMock()
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = sample_chat_data["chat_id"]
        update.effective_chat.type = sample_chat_data["chat_type"]
        update.effective_chat.title = sample_chat_data["title"]
        
        update.effective_user = update.message.from_user
        
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock Telegram callback context."""
        context = Mock(spec=CallbackContext)
        context.bot = Mock()
        context.bot.username = "TestBot"
        return context
    
    @pytest.mark.asyncio
    async def test_gpt_response_success(self, mock_update, mock_context, sample_config_data):
        """Test successful GPT response generation."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Test AI response",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            mock_history.add_message = Mock()
            
            result = await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=True
            )
            
            assert result == "Test AI response"
            mock_client.chat.completions.create.assert_called_once()
            mock_update.message.reply_text.assert_not_called()  # return_text=True
    
    @pytest.mark.asyncio
    async def test_gpt_response_with_message_override(self, mock_update, mock_context, sample_config_data):
        """Test GPT response with message text override."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Override response",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            
            await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                message_text_override="Custom prompt",
                return_text=False
            )
            
            # Verify the custom prompt was used
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            user_message = next((msg for msg in messages if msg["role"] == "user"), None)
            assert user_message is not None
            assert user_message["content"] == "Custom prompt"
            
            mock_update.message.reply_text.assert_called_once_with("Override response")
    
    @pytest.mark.asyncio
    async def test_gpt_response_long_message_truncation(self, mock_update, mock_context, sample_config_data):
        """Test that long responses are properly truncated."""
        long_response = "A" * 5000  # Longer than MAX_TELEGRAM_MESSAGE_LENGTH
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": long_response,
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            
            result = await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=True
            )
            
            assert len(result) <= 4096  # MAX_TELEGRAM_MESSAGE_LENGTH
            assert "[Message truncated due to length limit]" in result
    
    @pytest.mark.asyncio
    async def test_gpt_response_disabled_module(self, mock_update, mock_context):
        """Test GPT response when module is disabled."""
        disabled_config = {
            "config_modules": {
                "gpt": {
                    "enabled": False
                }
            }
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager:
            mock_config_manager.get_config = AsyncMock(return_value=disabled_config)
            
            result = await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=True
            )
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_gpt_response_mention_cleanup(self, mock_update, mock_context, sample_config_data):
        """Test that bot mentions are cleaned from mention responses."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Mention response",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            
            await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="mention",
                message_text_override="@TestBot hello there",
                return_text=False
            )
            
            # Verify the bot mention was removed
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            user_message = next((msg for msg in messages if msg["role"] == "user"), None)
            assert user_message is not None
            assert "@TestBot" not in user_message["content"]
            assert "hello there" in user_message["content"]


class TestImageAnalysis:
    """Test image analysis functionality."""
    
    @pytest.fixture
    def sample_image_bytes(self):
        """Create sample image bytes for testing."""
        # Create a simple 1x1 pixel image in bytes
        from PIL import Image
        from io import BytesIO
        
        img = Image.new('RGB', (100, 100), color='red')
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        return buffer.getvalue()
    
    @pytest.mark.asyncio
    async def test_optimize_image_resize(self, sample_image_bytes):
        """Test image optimization and resizing."""
        # Create a large image that needs resizing
        from PIL import Image
        from io import BytesIO
        
        large_img = Image.new('RGB', (2048, 2048), color='blue')
        buffer = BytesIO()
        large_img.save(buffer, format='JPEG')
        large_image_bytes = buffer.getvalue()
        
        optimized_bytes = await optimize_image(large_image_bytes)
        
        # Verify the optimized image is smaller and within size limits
        optimized_img = Image.open(BytesIO(optimized_bytes))
        assert max(optimized_img.size) <= 1024
        assert len(optimized_bytes) < len(large_image_bytes)
    
    @pytest.mark.asyncio
    async def test_analyze_image_success(self, sample_image_bytes, sample_config_data):
        """Test successful image analysis."""
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "This image shows a red square.",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.gpt.optimize_image') as mock_optimize:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_optimize.return_value = sample_image_bytes
            
            result = await analyze_image(
                image_bytes=sample_image_bytes,
                return_text=True
            )
            
            assert result == "This image shows a red square."
            mock_client.chat.completions.create.assert_called_once()
            
            # Verify the request included image data
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            user_message = next((msg for msg in messages if msg["role"] == "user"), None)
            assert user_message is not None
            assert "image_url" in str(user_message["content"])
    
    @pytest.mark.asyncio
    async def test_analyze_image_with_update_logging(self, sample_image_bytes, sample_config_data):
        """Test image analysis with update object for logging."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.from_user.username = "testuser"
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        mock_update.effective_chat.title = None
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Image description for logging",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.gpt.chat_logger') as mock_chat_logger, \
             patch('modules.gpt.optimize_image') as mock_optimize:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_optimize.return_value = sample_image_bytes
            
            result = await analyze_image(
                image_bytes=sample_image_bytes,
                update=mock_update,
                return_text=True
            )
            
            assert result == "Image description for logging"
            mock_chat_logger.info.assert_called_once()
            
            # Verify the log entry includes the image description prefix
            log_call = mock_chat_logger.info.call_args
            assert "[IMAGE DESCRIPTION]:" in log_call[0][0]


class TestSystemPrompts:
    """Test system prompt management and retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_system_prompt_default(self):
        """Test getting default system prompt when no config exists."""
        with patch('modules.gpt.config_manager') as mock_config_manager:
            mock_config_manager.get_config = AsyncMock(return_value={})
            
            prompt = await get_system_prompt("command", {})
            
            assert prompt == gpt.DEFAULT_PROMPTS["command"]
    
    @pytest.mark.asyncio
    async def test_get_system_prompt_custom_enabled(self, sample_config_data):
        """Test getting custom system prompt when custom config is enabled."""
        chat_config = sample_config_data.copy()
        chat_config["chat_metadata"]["custom_config_enabled"] = True
        chat_config["config_modules"]["gpt"]["overrides"]["command"]["system_prompt"] = "Custom prompt"
        
        with patch('modules.gpt.config_manager') as mock_config_manager:
            mock_config_manager.get_config = AsyncMock(return_value={})  # Global config
            
            prompt = await get_system_prompt("command", chat_config)
            
            assert prompt == "Custom prompt"
    
    @pytest.mark.asyncio
    async def test_get_system_prompt_custom_disabled(self, sample_config_data):
        """Test getting default prompt when custom config is disabled."""
        chat_config = sample_config_data.copy()
        chat_config["chat_metadata"]["custom_config_enabled"] = False
        chat_config["config_modules"]["gpt"]["overrides"]["command"]["system_prompt"] = "Custom prompt"
        
        with patch('modules.gpt.config_manager') as mock_config_manager:
            mock_config_manager.get_config = AsyncMock(return_value={})
            
            prompt = await get_system_prompt("command", chat_config)
            
            assert prompt == gpt.DEFAULT_PROMPTS["command"]
    
    @pytest.mark.asyncio
    async def test_get_system_prompt_validation_too_short(self, sample_config_data):
        """Test system prompt validation for too short prompts."""
        chat_config = sample_config_data.copy()
        chat_config["chat_metadata"]["custom_config_enabled"] = True
        chat_config["config_modules"]["gpt"]["overrides"]["command"]["system_prompt"] = "Hi"  # Too short
        
        with patch('modules.gpt.config_manager') as mock_config_manager:
            mock_config_manager.get_config = AsyncMock(return_value={})
            
            prompt = await get_system_prompt("command", chat_config)
            
            # Should fall back to default
            assert prompt == gpt.DEFAULT_PROMPTS["command"]
    
    @pytest.mark.asyncio
    async def test_get_system_prompt_validation_invalid_type(self, sample_config_data):
        """Test system prompt validation for invalid types."""
        chat_config = sample_config_data.copy()
        chat_config["chat_metadata"]["custom_config_enabled"] = True
        chat_config["config_modules"]["gpt"]["overrides"]["command"]["system_prompt"] = 123  # Invalid type
        
        with patch('modules.gpt.config_manager') as mock_config_manager:
            mock_config_manager.get_config = AsyncMock(return_value={})
            
            prompt = await get_system_prompt("command", chat_config)
            
            # Should fall back to default
            assert prompt == gpt.DEFAULT_PROMPTS["command"]


class TestContextMessages:
    """Test context message retrieval and processing."""
    
    @pytest.fixture
    def mock_update_with_history(self, sample_user_data, sample_chat_data):
        """Create a mock update with chat history."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.text = "Current message"
        update.message.from_user = Mock(spec=User)
        update.message.from_user.id = sample_user_data["user_id"]
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = sample_chat_data["chat_id"]
        update.effective_chat.type = sample_chat_data["chat_type"]
        
        return update
    
    @pytest.mark.asyncio
    async def test_get_context_messages_with_history(self, mock_update_with_history, sample_config_data):
        """Test getting context messages with chat history."""
        mock_context = Mock(spec=CallbackContext)
        
        # Mock chat history
        chat_history = [
            {"text": "Previous message 1", "is_user": True},
            {"text": "Bot response 1", "is_user": False},
            {"text": "Previous message 2", "is_user": True},
        ]
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_history.get_history.return_value = chat_history
            
            messages = await get_context_messages(
                update=mock_update_with_history,
                context=mock_context,
                response_type="command"
            )
            
            assert len(messages) == 3
            assert messages[0]["role"] == "user"
            assert messages[0]["content"] == "Previous message 1"
            assert messages[1]["role"] == "assistant"
            assert messages[1]["content"] == "Bot response 1"
            assert messages[2]["role"] == "user"
            assert messages[2]["content"] == "Previous message 2"
    
    @pytest.mark.asyncio
    async def test_get_context_messages_random_response_config(self, mock_update_with_history):
        """Test context messages for random responses with specific config."""
        mock_context = Mock(spec=CallbackContext)
        
        config_with_random = {
            "config_modules": {
                "chat_behavior": {
                    "enabled": True,
                    "overrides": {
                        "random_response_settings": {
                            "context_messages_count": 5
                        }
                    }
                }
            }
        }
        
        chat_history = [
            {"text": f"Message {i}", "is_user": True} for i in range(10)
        ]
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=config_with_random)
            mock_history.get_history.return_value = chat_history
            
            messages = await get_context_messages(
                update=mock_update_with_history,
                context=mock_context,
                response_type="random"
            )
            
            # Should get 5 messages as configured
            assert len(messages) == 5
    
    @pytest.mark.asyncio
    async def test_get_context_messages_no_history(self, mock_update_with_history, sample_config_data):
        """Test getting context messages when no history exists."""
        mock_context = Mock(spec=CallbackContext)
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_history.get_history.return_value = []
            
            messages = await get_context_messages(
                update=mock_update_with_history,
                context=mock_context,
                response_type="command"
            )
            
            assert len(messages) == 0


class TestCommandHandlers:
    """Test command handler functions."""
    
    @pytest.mark.asyncio
    async def test_ask_gpt_command_with_prompt(self, sample_config_data):
        """Test ask GPT command with provided prompt."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "/ask What is the weather like?"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "The weather is sunny today.",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            mock_history.add_message = Mock()
            
            await ask_gpt_command(mock_update, mock_context)
            
            mock_update.message.reply_text.assert_called_once_with("The weather is sunny today.")
    
    @pytest.mark.asyncio
    async def test_ask_gpt_command_no_prompt(self, sample_config_data):
        """Test ask GPT command without prompt (uses default)."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "/ask"  # No prompt provided
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Привіт! Як я можу вам допомогти?",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            mock_history.add_message = Mock()
            
            await ask_gpt_command(mock_update, mock_context)
            
            # Verify the default prompt was used
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            user_message = next((msg for msg in messages if msg["role"] == "user"), None)
            assert user_message is not None
            assert user_message["content"] == "Привіт! Як я можу вам допомогти?"
    
    @pytest.mark.asyncio
    async def test_answer_from_gpt_with_context(self, sample_config_data):
        """Test answer_from_gpt function with proper context."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test prompt"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Answer from GPT",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            
            result = await answer_from_gpt(
                prompt="Test prompt",
                update=mock_update,
                context=mock_context,
                return_text=True
            )
            
            assert result == "Answer from GPT"
    
    @pytest.mark.asyncio
    async def test_answer_from_gpt_no_context(self):
        """Test answer_from_gpt function without context (returns None)."""
        result = await answer_from_gpt(
            prompt="Test prompt",
            update=None,
            context=None,
            return_text=True
        )
        
        assert result is None


class TestConnectivityAndDiagnostics:
    """Test connectivity verification and diagnostic functions."""
    
    @pytest.mark.asyncio
    async def test_verify_api_key_valid(self):
        """Test API key verification with valid key."""
        with patch('modules.gpt.Config') as mock_config:
            mock_config.OPENROUTER_API_KEY = "sk-test-key-123"
            
            result = await verify_api_key()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self):
        """Test API key verification with invalid key."""
        with patch('modules.gpt.Config') as mock_config:
            mock_config.OPENROUTER_API_KEY = "invalid-key"
            
            result = await verify_api_key()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_verify_api_key_missing(self):
        """Test API key verification with missing key."""
        with patch('modules.gpt.Config') as mock_config:
            mock_config.OPENROUTER_API_KEY = None
            
            result = await verify_api_key()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_verify_connectivity_success(self):
        """Test successful connectivity verification."""
        with patch('socket.create_connection') as mock_socket:
            mock_socket.return_value = Mock()
            
            result = await verify_connectivity()
            
            assert result == "Connected"
            mock_socket.assert_called_once_with(("1.1.1.1", 53), timeout=3)
    
    @pytest.mark.asyncio
    async def test_verify_connectivity_failure(self):
        """Test connectivity verification failure."""
        with patch('socket.create_connection') as mock_socket:
            mock_socket.side_effect = OSError("Network unreachable")
            
            result = await verify_connectivity()
            
            assert result == "No connectivity"
    
    @pytest.mark.asyncio
    async def test_check_api_health_success(self):
        """Test successful API health check."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await check_api_health()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_check_api_health_failure(self):
        """Test API health check failure."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 500
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await check_api_health()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_check_api_health_exception(self):
        """Test API health check with exception."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection timeout")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await check_api_health()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_ensure_api_connectivity_cached(self):
        """Test API connectivity check with caching."""
        with patch('modules.gpt.run_api_diagnostics') as mock_diagnostics, \
             patch('modules.gpt.datetime') as mock_datetime:
            
            # Mock current time and last diagnostic time
            mock_now = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            # Set last diagnostic time to recent (within 5 minutes)
            gpt.last_diagnostic_time = datetime(2024, 1, 1, 11, 58, 0)
            gpt.last_diagnostic_result = {"status": "Connected"}
            
            result = await ensure_api_connectivity()
            
            assert result == "Connected"
            mock_diagnostics.assert_not_called()  # Should use cached result
    
    @pytest.mark.asyncio
    async def test_ensure_api_connectivity_expired_cache(self):
        """Test API connectivity check with expired cache."""
        with patch('modules.gpt.run_api_diagnostics') as mock_diagnostics, \
             patch('modules.gpt.datetime') as mock_datetime:
            
            # Mock current time
            mock_now = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            # Set last diagnostic time to old (more than 5 minutes)
            gpt.last_diagnostic_time = datetime(2024, 1, 1, 11, 50, 0)
            gpt.last_diagnostic_result = {"status": "Old result"}
            
            mock_diagnostics.return_value = {"status": "New result"}
            
            result = await ensure_api_connectivity()
            
            assert result == "New result"
            mock_diagnostics.assert_called_once()


class TestResponseTypeHandling:
    """Test different response type handling and processing."""
    
    @pytest.mark.asyncio
    async def test_analyze_response_type_mapping(self, sample_config_data):
        """Test that 'analyze' response type maps to 'summary' system prompt."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Analyze this text"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Analysis complete",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        # Add summary prompt to config
        config_with_summary = sample_config_data.copy()
        config_with_summary["config_modules"]["gpt"]["overrides"]["summary"] = {
            "system_prompt": "You are an analysis assistant."
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history, \
             patch('modules.gpt.get_system_prompt') as mock_get_prompt:
            
            mock_config_manager.get_config = AsyncMock(return_value=config_with_summary)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            mock_get_prompt.return_value = "You are an analysis assistant."
            
            await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="analyze",  # Should map to "summary"
                return_text=False
            )
            
            # Verify get_system_prompt was called with "summary" not "analyze"
            mock_get_prompt.assert_called_once_with("summary", config_with_summary)
    
    @pytest.mark.asyncio
    async def test_different_response_types_use_correct_prompts(self, sample_config_data):
        """Test that different response types use their specific prompts."""
        response_types = ["command", "mention", "private", "random", "weather"]
        
        for response_type in response_types:
            prompt = await get_system_prompt(response_type, sample_config_data)
            
            # Each response type should return a non-empty prompt
            assert prompt is not None
            assert len(prompt) > 0
            assert isinstance(prompt, str)


class TestPromptEngineering:
    """Test prompt engineering and context management."""
    
    @pytest.mark.asyncio
    async def test_system_prompt_with_context_injection(self, sample_config_data):
        """Test that system prompts are properly injected into message context."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test message"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Response with context",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        custom_system_prompt = "You are a specialized assistant for testing."
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history, \
             patch('modules.gpt.get_system_prompt') as mock_get_prompt:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            mock_get_prompt.return_value = custom_system_prompt
            
            await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=False
            )
            
            # Verify the system prompt was included in the messages
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            
            system_message = messages[0]
            assert system_message["role"] == "system"
            assert system_message["content"] == custom_system_prompt
    
    @pytest.mark.asyncio
    async def test_context_message_ordering(self, sample_config_data):
        """Test that context messages are properly ordered in the conversation."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Current message"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        # Mock conversation history
        chat_history = [
            {"text": "First user message", "is_user": True},
            {"text": "First bot response", "is_user": False},
            {"text": "Second user message", "is_user": True},
            {"text": "Second bot response", "is_user": False},
        ]
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Response with ordered context",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = chat_history
            
            await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=False
            )
            
            # Verify message ordering: system, context history (last 3 messages), current message
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            
            assert messages[0]["role"] == "system"
            # The context should include the last 3 messages from history
            assert messages[1]["role"] == "assistant"
            assert messages[1]["content"] == "First bot response"
            assert messages[2]["role"] == "user"
            assert messages[2]["content"] == "Second user message"
            assert messages[3]["role"] == "assistant"
            assert messages[3]["content"] == "Second bot response"
            assert messages[4]["role"] == "user"
            assert messages[4]["content"] == "Current message"
    
    @pytest.mark.asyncio
    async def test_temperature_and_max_tokens_configuration(self, sample_config_data):
        """Test that temperature and max_tokens are properly configured."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test message"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        # Configure custom temperature and max_tokens
        custom_config = sample_config_data.copy()
        custom_config["config_modules"]["gpt"]["overrides"]["command"]["temperature"] = 0.9
        custom_config["config_modules"]["gpt"]["overrides"]["command"]["max_tokens"] = 2000
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Configured response",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=custom_config)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            
            await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=False
            )
            
            # Verify the custom parameters were used
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["temperature"] == 0.9
            assert call_args[1]["max_tokens"] == 2000
    
    @pytest.mark.asyncio
    async def test_override_parameters_in_function_call(self, sample_config_data):
        """Test that function parameters override config parameters."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test message"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Override response",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            
            # Call with override parameters
            await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                max_tokens=500,  # Override config value
                temperature=0.1,  # Override config value
                return_text=False
            )
            
            # Verify the override parameters were used
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["temperature"] == 0.1
            assert call_args[1]["max_tokens"] == 500


class TestImageProcessing:
    """Test image processing and analysis functionality."""
    
    @pytest.mark.asyncio
    async def test_image_base64_encoding(self, sample_config_data):
        """Test that images are properly base64 encoded for API calls."""
        # Create a simple test image
        from PIL import Image
        from io import BytesIO
        
        test_img = Image.new('RGB', (50, 50), color='green')
        buffer = BytesIO()
        test_img.save(buffer, format='JPEG')
        test_image_bytes = buffer.getvalue()
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Green square image",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await analyze_image(
                image_bytes=test_image_bytes,
                return_text=True
            )
            
            assert result == "Green square image"
            
            # Verify the API call included base64 encoded image
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            user_message = next((msg for msg in messages if msg["role"] == "user"), None)
            
            assert user_message is not None
            content = user_message["content"]
            assert isinstance(content, list)
            
            # Find the image content
            image_content = next((item for item in content if item["type"] == "image_url"), None)
            assert image_content is not None
            assert "data:image/jpeg;base64," in image_content["image_url"]["url"]
    
    @pytest.mark.asyncio
    async def test_image_optimization_quality_settings(self):
        """Test that image optimization uses correct quality settings."""
        from PIL import Image
        from io import BytesIO
        
        # Create a test image
        original_img = Image.new('RGB', (200, 200), color='blue')
        buffer = BytesIO()
        original_img.save(buffer, format='JPEG', quality=100)
        original_bytes = buffer.getvalue()
        
        optimized_bytes = await optimize_image(original_bytes)
        
        # Verify the optimized image is smaller (due to compression)
        assert len(optimized_bytes) < len(original_bytes)
        
        # Verify the optimized image can be opened and has correct format
        optimized_img = Image.open(BytesIO(optimized_bytes))
        assert optimized_img.format == 'JPEG'
        assert optimized_img.size == (200, 200)  # Size should be preserved for small images
    
    @pytest.mark.asyncio
    async def test_image_analysis_with_custom_prompt(self, sample_config_data):
        """Test image analysis with custom system prompt."""
        from PIL import Image
        from io import BytesIO
        
        test_img = Image.new('RGB', (50, 50), color='red')
        buffer = BytesIO()
        test_img.save(buffer, format='JPEG')
        test_image_bytes = buffer.getvalue()
        
        # Add custom image analysis prompt to config
        custom_config = sample_config_data.copy()
        custom_config["config_modules"]["gpt"]["overrides"]["image_analysis"] = {
            "system_prompt": "You are a detailed image analyzer. Provide technical descriptions."
        }
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Technical analysis: Red RGB square, 50x50 pixels",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.gpt.get_system_prompt') as mock_get_prompt:
            
            mock_config_manager.get_config = AsyncMock(return_value=custom_config)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_prompt.return_value = "You are a detailed image analyzer. Provide technical descriptions."
            
            result = await analyze_image(
                image_bytes=test_image_bytes,
                return_text=True
            )
            
            assert result == "Technical analysis: Red RGB square, 50x50 pixels"
            # Verify that the image analysis was performed
            mock_client.chat.completions.create.assert_called_once()


class TestErrorScenarios:
    """Test various error scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_gpt_response_no_message_text(self, sample_config_data):
        """Test GPT response when update has no message text."""
        mock_update = Mock(spec=Update)
        mock_update.message = None  # No message
        
        mock_context = Mock()
        
        result = await gpt_response(
            update=mock_update,
            context=mock_context,
            response_type="command",
            return_text=True
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_gpt_response_empty_message_text(self, sample_config_data):
        """Test GPT response when message text is empty."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = ""  # Empty text
        
        mock_context = Mock()
        
        result = await gpt_response(
            update=mock_update,
            context=mock_context,
            response_type="command",
            return_text=True
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_image_analysis_error_handling(self):
        """Test image analysis error handling."""
        invalid_image_bytes = b"not an image"
        
        with patch('modules.gpt.handle_error') as mock_handle_error:
            result = await analyze_image(
                image_bytes=invalid_image_bytes,
                return_text=True
            )
            
            assert result == "Error analyzing image."
            mock_handle_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_messages_error_handling(self, sample_config_data):
        """Test context message retrieval error handling."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test message"
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config.side_effect = Exception("Config error")
            mock_history.get_history.return_value = []
            
            # Should not raise exception, should return empty list
            messages = await get_context_messages(
                update=mock_update,
                context=mock_context,
                response_type="command"
            )
            
            assert messages == []
    
    @pytest.mark.asyncio
    async def test_system_prompt_error_fallback(self):
        """Test system prompt fallback when config fails."""
        with patch('modules.gpt.config_manager') as mock_config_manager:
            mock_config_manager.get_config.side_effect = Exception("Config error")
            
            prompt = await get_system_prompt("command", {})
            
            # Should fall back to default prompt
            assert prompt == gpt.DEFAULT_PROMPTS["command"]


# Integration test for the complete flow
class TestGPTIntegration:
    """Integration tests for complete GPT workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_gpt_workflow(self, sample_user_data, sample_chat_data, sample_config_data):
        """Test complete GPT workflow from command to response."""
        # Create comprehensive mock update
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "/ask What is artificial intelligence?"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = sample_user_data["user_id"]
        mock_update.message.from_user.username = sample_user_data["username"]
        mock_update.message.date = datetime.now(timezone.utc)
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = sample_chat_data["chat_id"]
        mock_update.effective_chat.type = sample_chat_data["chat_type"]
        mock_update.effective_chat.title = sample_chat_data["title"]
        
        mock_update.effective_user = mock_update.message.from_user
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        # Mock API response
        mock_api_response = {
            "choices": [
                {
                    "message": {
                        "content": "Artificial intelligence (AI) is a branch of computer science that aims to create machines capable of intelligent behavior.",
                        "role": "assistant"
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 25,
                "total_tokens": 40
            },
            "model": "gpt-4o-mini"
        }
        
        # Mock chat history
        chat_history = [
            {"text": "Previous question about technology", "is_user": True},
            {"text": "Previous AI response about technology", "is_user": False}
        ]
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history, \
             patch('modules.gpt.chat_logger') as mock_chat_logger:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_api_response)
            mock_history.get_history.return_value = chat_history
            mock_history.add_message = Mock()
            
            # Execute the complete workflow
            await ask_gpt_command(mock_update, mock_context)
            
            # Verify all components were called correctly
            mock_config_manager.get_config.assert_called()
            mock_client.chat.completions.create.assert_called_once()
            mock_history.get_history.assert_called_once()
            mock_history.add_message.assert_called_once()
            mock_chat_logger.info.assert_called_once()
            mock_update.message.reply_text.assert_called_once()
            
            # Verify the response was sent
            sent_response = mock_update.message.reply_text.call_args[0][0]
            assert "Artificial intelligence" in sent_response
            
            # Verify the API call structure
            api_call_args = mock_client.chat.completions.create.call_args
            messages = api_call_args[1]["messages"]
            
            # Should have system prompt, context, and user message
            assert len(messages) >= 3
            assert messages[0]["role"] == "system"
            assert any(msg["role"] == "user" for msg in messages)

# ============================================================================
# Error Handling and Retry Logic Tests (Task 8.2)
# ============================================================================

class TestAPIErrorHandling:
    """Test API error handling scenarios including rate limits, timeouts, and invalid responses."""
    
    @pytest.mark.asyncio
    async def test_gpt_response_api_rate_limit_error(self, sample_config_data):
        """Test handling of API rate limit errors."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test message"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.from_user.username = "testuser"
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        mock_update.effective_chat.title = None
        
        mock_update.effective_user = mock_update.message.from_user
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        # Mock rate limit error
        rate_limit_error = Exception("HTTP 429: Rate limit exceeded")
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history, \
             patch('modules.gpt.handle_error') as mock_handle_error:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(side_effect=rate_limit_error)
            mock_history.get_history.return_value = []
            
            result = await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=True
            )
            
            assert result is None
            mock_handle_error.assert_called_once_with(rate_limit_error, mock_update, return_text=True)
    
    @pytest.mark.asyncio
    async def test_gpt_response_api_timeout_error(self, sample_config_data):
        """Test handling of API timeout errors."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test message"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.from_user.username = "testuser"
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_update.effective_user = mock_update.message.from_user
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        # Mock timeout error
        timeout_error = Exception("Request timeout")
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history, \
             patch('modules.gpt.handle_error') as mock_handle_error:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(side_effect=timeout_error)
            mock_history.get_history.return_value = []
            
            result = await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=True
            )
            
            assert result is None
            mock_handle_error.assert_called_once_with(timeout_error, mock_update, return_text=True)
    
    @pytest.mark.asyncio
    async def test_gpt_response_invalid_api_response(self, sample_config_data):
        """Test handling of invalid API responses."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test message"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.from_user.username = "testuser"
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_update.effective_user = mock_update.message.from_user
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        # Mock invalid response (missing required fields)
        invalid_response = {"error": "Invalid request"}
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history, \
             patch('modules.gpt.handle_error') as mock_handle_error:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=invalid_response)
            mock_history.get_history.return_value = []
            
            result = await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=True
            )
            
            assert result is None
            mock_handle_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_gpt_response_network_connection_error(self, sample_config_data):
        """Test handling of network connection errors."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test message"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.from_user.username = "testuser"
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_update.effective_user = mock_update.message.from_user
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        # Mock network connection error
        connection_error = ConnectionError("Network connection failed")
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history, \
             patch('modules.gpt.handle_error') as mock_handle_error:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(side_effect=connection_error)
            mock_history.get_history.return_value = []
            
            result = await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=True
            )
            
            assert result is None
            mock_handle_error.assert_called_once_with(connection_error, mock_update, return_text=True)


class TestErrorDiagnostics:
    """Test error diagnostic and connectivity checking functionality."""
    
    @pytest.mark.asyncio
    async def test_handle_error_with_connectivity_diagnosis(self):
        """Test that handle_error performs connectivity diagnosis."""
        mock_update = Mock(spec=Update)
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 12345
        mock_update.effective_chat = Mock()
        mock_update.effective_chat.id = 12345
        mock_update.message = Mock()
        mock_update.message.reply_text = AsyncMock()
        
        test_error = Exception("Test error")
        
        with patch('modules.gpt.ensure_api_connectivity') as mock_ensure_connectivity, \
             patch('modules.gpt.ErrorHandler') as mock_error_handler:
            
            mock_ensure_connectivity.return_value = "No internet connectivity"
            mock_error_handler.handle_error = AsyncMock()
            
            await gpt.handle_error(test_error, mock_update, return_text=False)
            
            mock_ensure_connectivity.assert_called_once()
            mock_error_handler.handle_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_error_different_diagnosis_messages(self):
        """Test different error diagnosis messages and corresponding feedback."""
        mock_update = Mock(spec=Update)
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 12345
        mock_update.effective_chat = Mock()
        mock_update.effective_chat.id = 12345
        mock_update.message = Mock()
        mock_update.message.reply_text = AsyncMock()
        
        test_error = Exception("Test error")
        
        diagnosis_scenarios = [
            ("No internet connectivity", "Вибачте, відсутнє з'єднання з Інтернетом. Спробуйте пізніше."),
            ("DNS resolution issues", "Вибачте, проблема з DNS-розпізнаванням. Спробуйте пізніше."),
            ("API endpoint unreachable", "Вибачте, сервіс GPT тимчасово недоступний. Спробуйте пізнише."),
            ("Unknown error", "Вибачте, помилка з'єднання з сервісом GPT. Спробуйте пізнише.")
        ]
        
        for diagnosis, expected_message in diagnosis_scenarios:
            with patch('modules.gpt.ensure_api_connectivity') as mock_ensure_connectivity, \
                 patch('modules.gpt.ErrorHandler') as mock_error_handler:
                
                mock_ensure_connectivity.return_value = diagnosis
                mock_error_handler.handle_error = AsyncMock()
                
                await gpt.handle_error(test_error, mock_update, return_text=False)
                
                # Verify the error handler was called with the correct feedback message
                call_args = mock_error_handler.handle_error.call_args
                feedback_message = call_args[1]["feedback_message"]
                assert feedback_message == expected_message
    
    @pytest.mark.asyncio
    async def test_handle_error_return_text_mode(self):
        """Test error handling in return_text mode (no message sending)."""
        mock_update = Mock(spec=Update)
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 12345
        mock_update.effective_chat = Mock()
        mock_update.effective_chat.id = 12345
        mock_update.message = Mock()
        mock_update.message.reply_text = AsyncMock()
        
        test_error = Exception("Test error")
        
        with patch('modules.gpt.ensure_api_connectivity') as mock_ensure_connectivity, \
             patch('modules.gpt.ErrorHandler') as mock_error_handler:
            
            mock_ensure_connectivity.return_value = "Connected"
            mock_error_handler.handle_error = AsyncMock()
            
            await gpt.handle_error(test_error, mock_update, return_text=True)
            
            # Verify the error handler was called with correct parameters
            call_args = mock_error_handler.handle_error.call_args
            assert call_args[1]["error"] == test_error
            assert call_args[1]["update"] == mock_update
    
    @pytest.mark.asyncio
    async def test_handle_error_no_update_object(self):
        """Test error handling when no update object is provided."""
        test_error = Exception("Test error")
        
        with patch('modules.gpt.ensure_api_connectivity') as mock_ensure_connectivity, \
             patch('modules.gpt.ErrorHandler') as mock_error_handler:
            
            mock_ensure_connectivity.return_value = "Connected"
            mock_error_handler.handle_error = AsyncMock()
            
            await gpt.handle_error(test_error, None, return_text=True)
            
            # Verify the error handler was called with None update
            call_args = mock_error_handler.handle_error.call_args
            assert call_args[1]["error"] == test_error
            assert call_args[1]["update"] is None


class TestConnectivityAndHealthChecks:
    """Test connectivity verification and health check functionality."""
    
    @pytest.mark.asyncio
    async def test_ensure_api_connectivity_caching_mechanism(self):
        """Test that API connectivity checks are properly cached."""
        with patch('modules.gpt.run_api_diagnostics') as mock_diagnostics, \
             patch('modules.gpt.datetime') as mock_datetime:
            
            # Mock current time
            mock_now = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            # Set up initial state - no previous diagnostic
            gpt.last_diagnostic_result = None
            gpt.last_diagnostic_time = datetime.min
            
            mock_diagnostics.return_value = {"status": "Connected"}
            
            # First call should run diagnostics
            result1 = await ensure_api_connectivity()
            assert result1 == "Connected"
            assert mock_diagnostics.call_count == 1
            
            # Second call within 5 minutes should use cache
            mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 2, 0)  # 2 minutes later
            result2 = await ensure_api_connectivity()
            assert result2 == "Connected"
            assert mock_diagnostics.call_count == 1  # Should not increase
            
            # Third call after 5 minutes should run diagnostics again
            mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 6, 0)  # 6 minutes later
            result3 = await ensure_api_connectivity()
            assert result3 == "Connected"
            assert mock_diagnostics.call_count == 2  # Should increase
    
    @pytest.mark.asyncio
    async def test_ensure_api_connectivity_failed_status_forces_recheck(self):
        """Test that failed connectivity status forces immediate recheck."""
        with patch('modules.gpt.run_api_diagnostics') as mock_diagnostics, \
             patch('modules.gpt.datetime') as mock_datetime:
            
            # Mock current time
            mock_now = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            # Set up initial failed state
            gpt.last_diagnostic_result = {"status": "No internet connectivity"}
            gpt.last_diagnostic_time = datetime(2024, 1, 1, 11, 59, 0)  # 1 minute ago
            
            mock_diagnostics.return_value = {"status": "Connected"}
            
            # Should run diagnostics despite recent check due to failed status
            result = await ensure_api_connectivity()
            assert result == "Connected"
            mock_diagnostics.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verify_connectivity_success(self):
        """Test successful connectivity verification."""
        with patch('socket.create_connection') as mock_socket:
            mock_socket.return_value = Mock()
            
            result = await verify_connectivity()
            
            assert result == "Connected"
            mock_socket.assert_called_once_with(("1.1.1.1", 53), timeout=3)
    
    @pytest.mark.asyncio
    async def test_verify_connectivity_failure(self):
        """Test connectivity verification failure."""
        with patch('socket.create_connection') as mock_socket:
            mock_socket.side_effect = OSError("Network unreachable")
            
            result = await verify_connectivity()
            
            assert result == "No connectivity"
    
    @pytest.mark.asyncio
    async def test_check_api_health_with_openrouter(self):
        """Test API health check with OpenRouter configuration."""
        with patch('modules.gpt.Config') as mock_config, \
             patch('httpx.AsyncClient') as mock_client_class:
            
            mock_config.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
            mock_config.OPENROUTER_API_KEY = "test-key"
            
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await check_api_health()
            
            assert result is True
            # Verify the correct endpoint was called
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            assert "openrouter.ai" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_check_api_health_with_openai(self):
        """Test API health check with OpenAI configuration."""
        with patch('modules.gpt.Config') as mock_config, \
             patch('modules.gpt.USE_OPENROUTER', False), \
             patch('httpx.AsyncClient') as mock_client_class:
            
            mock_config.OPENROUTER_BASE_URL = None  # Use OpenAI
            mock_config.OPENROUTER_API_KEY = "test-key"
            
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await check_api_health()
            
            assert result is True
            # Verify the correct endpoint was called
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            # Parse the URL and validate the host properly
            from urllib.parse import urlparse
            url = call_args[0][0]
            parsed_url = urlparse(url)
            
            # Check if it's an OpenAI endpoint
            is_openai = (parsed_url.hostname and 
                        (parsed_url.hostname == "api.openai.com" or 
                         parsed_url.hostname.endswith(".openai.com")))
            
            assert is_openai, f"Invalid endpoint: {url}"


class TestImageAnalysisErrorHandling:
    """Test error handling in image analysis functionality."""
    
    @pytest.mark.asyncio
    async def test_analyze_image_invalid_image_data(self):
        """Test image analysis with invalid image data."""
        invalid_image_bytes = b"not an image"
        
        with patch('modules.gpt.handle_error') as mock_handle_error:
            result = await analyze_image(
                image_bytes=invalid_image_bytes,
                return_text=True
            )
            
            assert result == "Error analyzing image."
            mock_handle_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_image_api_error(self, sample_config_data):
        """Test image analysis when API call fails."""
        from PIL import Image
        from io import BytesIO
        
        # Create valid image bytes
        test_img = Image.new('RGB', (50, 50), color='red')
        buffer = BytesIO()
        test_img.save(buffer, format='JPEG')
        test_image_bytes = buffer.getvalue()
        
        api_error = Exception("API call failed")
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.gpt.optimize_image') as mock_optimize, \
             patch('modules.gpt.handle_error') as mock_handle_error:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_optimize.return_value = test_image_bytes
            mock_client.chat.completions.create = AsyncMock(side_effect=api_error)
            
            result = await analyze_image(
                image_bytes=test_image_bytes,
                return_text=True
            )
            
            assert result == "Error analyzing image."
            mock_handle_error.assert_called_once_with(api_error, None, return_text=False)
    
    @pytest.mark.asyncio
    async def test_optimize_image_invalid_format(self):
        """Test image optimization with invalid image format."""
        invalid_image_bytes = b"invalid image data"
        
        with pytest.raises(Exception):
            await optimize_image(invalid_image_bytes)
    
    @pytest.mark.asyncio
    async def test_optimize_image_large_image_resize(self):
        """Test that large images are properly resized during optimization."""
        from PIL import Image
        from io import BytesIO
        
        # Create a very large image
        large_img = Image.new('RGB', (3000, 3000), color='blue')
        buffer = BytesIO()
        large_img.save(buffer, format='JPEG')
        large_image_bytes = buffer.getvalue()
        
        optimized_bytes = await optimize_image(large_image_bytes)
        
        # Verify the optimized image is within size limits
        optimized_img = Image.open(BytesIO(optimized_bytes))
        assert max(optimized_img.size) <= 1024
        assert len(optimized_bytes) < len(large_image_bytes)


class TestFallbackAndGracefulDegradation:
    """Test fallback strategies and graceful degradation scenarios."""
    
    @pytest.mark.asyncio
    async def test_gpt_response_config_loading_failure(self):
        """Test GPT response when configuration loading fails."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test message"
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.from_user.username = "testuser"
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_update.effective_user = mock_update.message.from_user
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        config_error = Exception("Config loading failed")
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.handle_error') as mock_handle_error:
            
            mock_config_manager.get_config = AsyncMock(side_effect=config_error)
            
            result = await gpt_response(
                update=mock_update,
                context=mock_context,
                response_type="command",
                return_text=True
            )
            
            assert result is None
            mock_handle_error.assert_called_once_with(config_error, mock_update, return_text=True)
    
    @pytest.mark.asyncio
    async def test_get_system_prompt_fallback_on_error(self):
        """Test system prompt fallback when configuration access fails."""
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.error_logger') as mock_error_logger:
            
            mock_config_manager.get_config = AsyncMock(side_effect=Exception("Config error"))
            
            prompt = await get_system_prompt("command", {})
            
            # Should fall back to default prompt
            assert prompt == gpt.DEFAULT_PROMPTS["command"]
            mock_error_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_context_messages_error_recovery(self, sample_config_data):
        """Test context message retrieval error recovery."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "Test message"
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.utils.chat_history_manager') as mock_history, \
             patch('modules.logger.error_logger') as mock_error_logger:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_history.get_history.side_effect = Exception("History access failed")
            
            # Should not raise exception, should return empty list
            messages = await get_context_messages(
                update=mock_update,
                context=mock_context,
                response_type="command"
            )
            
            assert messages == []
            mock_error_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_answer_from_gpt_no_context_fallback(self):
        """Test answer_from_gpt fallback when no context is provided."""
        result = await answer_from_gpt(
            prompt="Test prompt",
            update=None,
            context=None,
            return_text=True
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_ask_gpt_command_empty_message_fallback(self, sample_config_data):
        """Test ask GPT command fallback when message is empty."""
        mock_update = Mock(spec=Update)
        mock_update.message = Mock(spec=Message)
        mock_update.message.text = "/ask"  # No prompt provided
        mock_update.message.from_user = Mock(spec=User)
        mock_update.message.from_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_update.effective_chat = Mock(spec=Chat)
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.type = "private"
        
        mock_context = Mock()
        mock_context.bot = Mock()
        mock_context.bot.username = "TestBot"
        
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Default response",
                        "role": "assistant"
                    }
                }
            ]
        }
        
        with patch('modules.gpt.config_manager') as mock_config_manager, \
             patch('modules.gpt.client') as mock_client, \
             patch('modules.utils.chat_history_manager') as mock_history:
            
            mock_config_manager.get_config = AsyncMock(return_value=sample_config_data)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_history.get_history.return_value = []
            mock_history.add_message = Mock()
            
            await ask_gpt_command(mock_update, mock_context)
            
            # Verify the default prompt was used
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            user_message = next((msg for msg in messages if msg["role"] == "user"), None)
            assert user_message is not None
            assert user_message["content"] == "Привіт! Як я можу вам допомогти?"


class TestRetryMechanisms:
    """Test retry mechanisms and exponential backoff (if implemented)."""
    
    @pytest.mark.asyncio
    async def test_openai_client_retry_on_failure(self):
        """Test that OpenAI client handles retries appropriately."""
        client = OpenAIAsyncClient(
            api_key="test-key",
            base_url="https://api.openai.com/v1"
        )
        
        # Mock first call fails, second succeeds
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            "choices": [{"message": {"content": "Success", "role": "assistant"}}]
        }
        mock_response_success.raise_for_status.return_value = None
        
        mock_response_failure = Mock()
        mock_response_failure.raise_for_status.side_effect = Exception("Temporary failure")
        
        with patch.object(client._client, 'post') as mock_post:
            # First call fails, second succeeds
            mock_post.side_effect = [mock_response_failure, mock_response_success]
            
            # The first call should raise an exception (no built-in retry in current implementation)
            with pytest.raises(Exception, match="Temporary failure"):
                await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "Test"}],
                    max_tokens=100,
                    temperature=0.7
                )
    
    @pytest.mark.asyncio
    async def test_api_health_check_retry_behavior(self):
        """Test API health check behavior on failures."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            
            # First call fails, second succeeds
            mock_response_fail = Mock()
            mock_response_fail.status_code = 500
            mock_response_success = Mock()
            mock_response_success.status_code = 200
            
            mock_client.get.side_effect = [mock_response_fail, mock_response_success]
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # First call should return False
            result1 = await check_api_health()
            assert result1 is False
            
            # Second call should return True
            result2 = await check_api_health()
            assert result2 is True
    
    @pytest.mark.asyncio
    async def test_connectivity_verification_multiple_attempts(self):
        """Test connectivity verification with multiple attempts."""
        with patch('socket.create_connection') as mock_socket:
            # First attempt fails, second succeeds
            mock_socket.side_effect = [OSError("First attempt failed"), Mock()]
            
            # First call should fail
            result1 = await verify_connectivity()
            assert result1 == "No connectivity"
            
            # Second call should succeed
            result2 = await verify_connectivity()
            assert result2 == "Connected"


class TestErrorContextAndLogging:
    """Test error context creation and logging functionality."""
    
    @pytest.mark.asyncio
    async def test_handle_error_context_creation(self):
        """Test that handle_error creates proper error context."""
        mock_update = Mock(spec=Update)
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 12345
        mock_update.effective_chat = Mock()
        mock_update.effective_chat.id = -1001234567890
        mock_update.message = Mock()
        mock_update.message.reply_text = AsyncMock()
        
        test_error = Exception("Test error")
        
        with patch('modules.gpt.ensure_api_connectivity') as mock_ensure_connectivity, \
             patch('modules.gpt.ErrorHandler') as mock_error_handler:
            
            mock_ensure_connectivity.return_value = "Connected"
            mock_error_handler.handle_error = AsyncMock()
            
            await gpt.handle_error(test_error, mock_update, return_text=True)
            
            # Verify the error handler was called with correct parameters
            call_args = mock_error_handler.handle_error.call_args
            assert call_args[1]["error"] == test_error
            assert call_args[1]["update"] == mock_update
            assert call_args[1]["context"] is None  # Context is passed as None in actual implementation
    
    @pytest.mark.asyncio
    async def test_handle_error_with_partial_update_info(self):
        """Test error handling with partial update information."""
        mock_update = Mock(spec=Update)
        mock_update.effective_user = None  # Missing user info
        mock_update.effective_chat = Mock()
        mock_update.effective_chat.id = 12345
        mock_update.message = Mock()
        mock_update.message.reply_text = AsyncMock()
        
        test_error = Exception("Test error")
        
        with patch('modules.gpt.ensure_api_connectivity') as mock_ensure_connectivity, \
             patch('modules.gpt.ErrorHandler') as mock_error_handler:
            
            mock_ensure_connectivity.return_value = "Connected"
            mock_error_handler.handle_error = AsyncMock()
            
            await gpt.handle_error(test_error, mock_update, return_text=False)
            
            # Verify the error handler was called with correct parameters
            call_args = mock_error_handler.handle_error.call_args
            assert call_args[1]["error"] == test_error
            assert call_args[1]["update"] == mock_update
    
    @pytest.mark.asyncio
    async def test_error_logging_integration(self):
        """Test that errors are properly logged through the error handling system."""
        mock_update = Mock(spec=Update)
        mock_update.effective_user = Mock()
        mock_update.effective_user.id = 12345
        mock_update.effective_chat = Mock()
        mock_update.effective_chat.id = 12345
        mock_update.message = Mock()
        mock_update.message.reply_text = AsyncMock()
        
        test_error = ValueError("Test validation error")
        
        with patch('modules.gpt.ensure_api_connectivity') as mock_ensure_connectivity, \
             patch('modules.gpt.ErrorHandler') as mock_error_handler:
            
            mock_ensure_connectivity.return_value = "Connected"
            mock_error_handler.handle_error = AsyncMock()
            
            await gpt.handle_error(test_error, mock_update, return_text=False)
            
            # Verify ErrorHandler.handle_error was called with the original error
            call_args = mock_error_handler.handle_error.call_args
            assert call_args[1]["error"] == test_error  # Error should be passed as keyword argument
            assert call_args[1]["update"] == mock_update
            assert call_args[1]["propagate"] == True