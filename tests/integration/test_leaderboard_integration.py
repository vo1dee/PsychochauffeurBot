"""
Integration tests for leaderboard functionality.

Tests the complete leaderboard flow from command handler to database.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from modules.handlers.utility_commands import leaderboard_command
from modules.leveling_models import UserProfile, Achievement


@pytest.mark.asyncio
async def test_leaderboard_integration_success():
    """Test successful leaderboard integration with mocked service."""
    # Create mock update and context
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = 12345
    
    # Create mock achievements
    achievement1 = Achievement(
        id="chatterbox",
        title="Chatterbox", 
        description="Send 100 messages",
        emoji="💬",
        sticker="💬",
        condition_type="messages",
        condition_value=100,
        category="activity"
    )
    
    # Create mock user profiles
    profile1 = UserProfile(
        user_id=1001,
        username="alice",
        level=5,
        xp=1000,
        next_level_xp=1200,
        progress_percentage=83.3,
        achievements=[achievement1],
        stats={"messages_count": 150, "links_shared": 10, "thanks_received": 8},
        rank=1
    )
    
    profile2 = UserProfile(
        user_id=1002,
        username="bob",
        level=3,
        xp=500,
        next_level_xp=600,
        progress_percentage=83.3,
        achievements=[],
        stats={"messages_count": 120, "links_shared": 5, "thanks_received": 3},
        rank=2
    )
    
    leaderboard = [profile1, profile2]
    
    # Create mock leveling service
    leveling_service = MagicMock()
    leveling_service.is_enabled.return_value = True
    leveling_service.get_leaderboard = AsyncMock(return_value=leaderboard)
    
    # Create mock service registry
    service_registry = MagicMock()
    service_registry.get_service.return_value = leveling_service
    
    # Create mock context
    context = MagicMock()
    context.bot_data = {'service_registry': service_registry}
    context.args = []
    
    # Execute the command
    await leaderboard_command(update, context)
    
    # Verify service calls
    service_registry.get_service.assert_called_once_with('user_leveling_service')
    leveling_service.is_enabled.assert_called_once()
    leveling_service.get_leaderboard.assert_awaited_once_with(12345, 10)
    
    # Verify response
    update.message.reply_text.assert_awaited_once()
    call_args = update.message.reply_text.call_args
    message_text = call_args[0][0]
    
    # Verify message content
    assert "🏆 **Chat Leaderboard (Top 2)**" in message_text
    assert "🥇 **alice**" in message_text
    assert "Level 5 • 1,000 XP" in message_text
    assert "💬" in message_text  # Achievement emoji for rank 1
    assert "🥈 **bob**" in message_text
    assert "Level 3 • 500 XP" in message_text
    
    # Verify parse_mode
    assert call_args[1]['parse_mode'] == 'Markdown'


@pytest.mark.asyncio
async def test_leaderboard_integration_with_custom_limit():
    """Test leaderboard integration with custom limit."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = 12345
    
    leveling_service = MagicMock()
    leveling_service.is_enabled.return_value = True
    leveling_service.get_leaderboard = AsyncMock(return_value=[])
    
    service_registry = MagicMock()
    service_registry.get_service.return_value = leveling_service
    
    context = MagicMock()
    context.bot_data = {'service_registry': service_registry}
    context.args = ['15']  # Custom limit
    
    await leaderboard_command(update, context)
    
    # Verify custom limit is passed
    leveling_service.get_leaderboard.assert_awaited_once_with(12345, 15)


@pytest.mark.asyncio
async def test_leaderboard_integration_empty_result():
    """Test leaderboard integration with empty result."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = 12345
    
    leveling_service = MagicMock()
    leveling_service.is_enabled.return_value = True
    leveling_service.get_leaderboard = AsyncMock(return_value=[])
    
    service_registry = MagicMock()
    service_registry.get_service.return_value = leveling_service
    
    context = MagicMock()
    context.bot_data = {'service_registry': service_registry}
    context.args = []
    
    await leaderboard_command(update, context)
    
    # Verify empty message
    update.message.reply_text.assert_awaited_once_with("📊 No leaderboard data available yet.")


@pytest.mark.asyncio
async def test_leaderboard_integration_service_disabled():
    """Test leaderboard integration when service is disabled."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    
    leveling_service = MagicMock()
    leveling_service.is_enabled.return_value = False
    
    service_registry = MagicMock()
    service_registry.get_service.return_value = leveling_service
    
    context = MagicMock()
    context.bot_data = {'service_registry': service_registry}
    context.args = []
    
    await leaderboard_command(update, context)
    
    # Verify disabled message
    update.message.reply_text.assert_awaited_once_with("❌ Leveling system is disabled.")
    
    # Verify get_leaderboard was not called
    leveling_service.get_leaderboard.assert_not_called()