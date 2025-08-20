"""Integration tests for the analyze command."""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from telegram import Update, Message, Chat, User
from telegram.ext import CallbackContext

from modules.gpt import analyze_command

@pytest.fixture
def update_fixture():
    """Fixture for creating a test update."""
    update = Update(
        update_id=1,
        message=Message(
            message_id=1,
            date=datetime.now(),
            chat=Chat(id=-10012345678, type='group'),
            from_user=User(id=12345, first_name='Test', is_bot=False, username='testuser'),
            text='/analyze date 2025-08-20'
        )
    )
    return update

@pytest.fixture
def context_fixture():
    """Fixture for creating a test context."""
    context = MagicMock(spec=CallbackContext)
    context.args = ['date', '2025-08-20']
    return context

@pytest.mark.asyncio
async def test_analyze_command_date(update_fixture, context_fixture):
    """Test the full flow of the analyze command with a date parameter."""
    # Mock the database response
    mock_messages = [
        (datetime(2025, 8, 20, 10, 30, 0), 'testuser', 'Test message 1'),
        (datetime(2025, 8, 20, 11, 30, 0), 'testuser', 'Test message 2'),
    ]
    
    # Patch the message retrieval and GPT analysis
    with patch('modules.chat_analysis.get_messages_for_chat_single_date', 
              return_value=mock_messages) as mock_get_messages,\n         patch('modules.gpt.analyze_with_gpt', 
              return_value="Test analysis result") as mock_analyze:
        
        await analyze_command(update_fixture, context_fixture)
        
        # Verify the message retrieval was called with correct parameters
        mock_get_messages.assert_called_once_with(
            chat_id=-10012345678,
            target_date=date(2025, 8, 20)
        )
        
        # Verify the analysis was performed
        mock_analyze.assert_called_once()
        
        # Verify the result was sent to the chat
        update_fixture.message.reply_text.assert_called_once()
        assert "Test analysis result" in update_fixture.message.reply_text.call_args[0][0]
