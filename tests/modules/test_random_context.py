#!/usr/bin/env python3
"""
Test for random response context messages count functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from modules.gpt import get_context_messages
from config.config_manager import ConfigManager

@pytest.fixture
def mock_config_manager():
    """Mock config manager for testing."""
    with patch('modules.gpt.config_manager') as mock_cm:
        # Mock the async get_config method
        mock_cm.get_config = AsyncMock()
        
        # Mock global config
        mock_cm.get_config.return_value = {
            "config_modules": {
                "chat_behavior": {
                    "enabled": True,
                    "overrides": {
                        "random_response_settings": {
                            "enabled": True,
                            "context_messages_count": 5
                        }
                    }
                }
            }
        }
        yield mock_cm

@pytest.fixture
def mock_update():
    """Mock Telegram update object."""
    update = MagicMock()
    update.effective_chat.id = -100123456789
    update.effective_chat.type = "supergroup"
    update.message.text = "Test message"
    return update

@pytest.fixture
def mock_context():
    """Mock Telegram context object."""
    context = MagicMock()
    context.chat_data = {
        'message_history': [
            {'text': 'Message 1', 'is_user': True},
            {'text': 'Message 2', 'is_user': False},
            {'text': 'Message 3', 'is_user': True},
            {'text': 'Message 4', 'is_user': False},
            {'text': 'Message 5', 'is_user': True},
            {'text': 'Message 6', 'is_user': False},
        ]
    }
    return context

@pytest.mark.asyncio
async def test_random_response_context_count(mock_config_manager, mock_update, mock_context):
    """Test that random responses use the correct context messages count."""
    
    # Mock chat config with custom context_messages_count
    mock_config_manager.get_config.return_value = {
        "config_modules": {
            "chat_behavior": {
                "enabled": True,
                "overrides": {
                    "random_response_settings": {
                        "enabled": True,
                        "context_messages_count": 3
                    }
                }
            }
        }
    }
    
    # Get context messages for random response
    messages = await get_context_messages(mock_update, mock_context, "random")
    
    # Should include current message + 3 previous messages (total 4)
    assert len(messages) == 4
    
    # Check that we got the most recent messages
    assert messages[0]["content"] == "Message 4"  # Oldest
    assert messages[1]["content"] == "Message 5"  # Middle
    assert messages[2]["content"] == "Message 6"  # Newest previous
    assert messages[3]["content"] == "Test message"  # Current

@pytest.mark.asyncio
async def test_command_response_context_count(mock_config_manager, mock_update, mock_context):
    """Test that command responses use GPT module context count."""
    
    # Mock chat config with GPT module context count
    mock_config_manager.get_config.return_value = {
        "config_modules": {
            "gpt": {
                "context_messages_count": 2
            },
            "chat_behavior": {
                "enabled": True,
                "overrides": {
                    "random_response_settings": {
                        "enabled": True,
                        "context_messages_count": 5
                    }
                }
            }
        }
    }
    
    # Get context messages for command response
    messages = await get_context_messages(mock_update, mock_context, "command")
    
    # Should include current message + 2 previous messages (total 3)
    assert len(messages) == 3
    
    # Check that we got the most recent messages
    assert messages[0]["content"] == "Message 5"  # Oldest
    assert messages[1]["content"] == "Message 6"  # Newest previous
    assert messages[2]["content"] == "Test message"  # Current

@pytest.mark.asyncio
async def test_fallback_to_global_config(mock_config_manager, mock_update, mock_context):
    """Test fallback to global config when chat_behavior is disabled."""
    
    # Mock chat config with disabled chat_behavior
    mock_config_manager.get_config.return_value = {
        "config_modules": {
            "chat_behavior": {
                "enabled": False,
                "overrides": {
                    "random_response_settings": {
                        "enabled": True,
                        "context_messages_count": 1
                    }
                }
            }
        }
    }
    
    # Get context messages for random response
    messages = await get_context_messages(mock_update, mock_context, "random")
    
    # Should fallback to global config (5 messages) + current message
    assert len(messages) == 6

if __name__ == "__main__":
    pytest.main([__file__]) 