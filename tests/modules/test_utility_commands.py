import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from modules.handlers import utility_commands
from modules.leveling_models import UserProfile, Achievement
import typing

@pytest.mark.asyncio
async def test_cat_command_calls_cat(mock_update: typing.Any, mock_context: typing.Any) -> None:
    with patch("modules.handlers.utility_commands._cat", new=AsyncMock()) as mock_cat:
        await utility_commands.cat_command(mock_update, mock_context)
        mock_cat.assert_awaited_once_with(mock_update, mock_context)

@pytest.mark.asyncio
async def test_screenshot_command_calls_screenshot(mock_update: typing.Any, mock_context: typing.Any) -> None:
    with patch("modules.handlers.utility_commands._screenshot", new=AsyncMock()) as mock_screenshot:
        await utility_commands.screenshot_command(mock_update, mock_context)
        mock_screenshot.assert_awaited_once_with(mock_update, mock_context)

@pytest.mark.asyncio
async def test_count_command_calls_count(mock_update: typing.Any, mock_context: typing.Any) -> None:
    with patch("modules.handlers.utility_commands._count", new=AsyncMock()) as mock_count:
        await utility_commands.count_command(mock_update, mock_context)
        mock_count.assert_awaited_once_with(mock_update, mock_context)

@pytest.mark.asyncio
async def test_missing_command_calls_missing() -> None:
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.utility_commands._missing", new=AsyncMock()) as mock_missing:
        await utility_commands.missing_command(update, context)
        mock_missing.assert_awaited_once_with(update, context)

@pytest.mark.asyncio
async def test_error_report_command_calls_error_report(mock_update: typing.Any, mock_context: typing.Any) -> None:
    with patch("modules.handlers.utility_commands._error_report", new=AsyncMock()) as mock_error_report:
        await utility_commands.error_report_command(mock_update, mock_context)
        mock_error_report.assert_awaited_once_with(mock_update, mock_context)


@pytest.mark.asyncio
async def test_leaderboard_command_no_service_registry() -> None:
    """Test leaderboard command when service registry is not available."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    
    context = MagicMock()
    context.bot_data = {}
    
    await utility_commands.leaderboard_command(update, context)
    
    update.message.reply_text.assert_awaited_once_with("❌ Leveling system is not available.")


@pytest.mark.asyncio
async def test_leaderboard_command_no_leveling_service() -> None:
    """Test leaderboard command when leveling service is not available."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    
    service_registry = MagicMock()
    service_registry.get_service.side_effect = ValueError("Service not found")
    
    context = MagicMock()
    context.bot_data = {'service_registry': service_registry}
    
    await utility_commands.leaderboard_command(update, context)
    
    update.message.reply_text.assert_awaited_once_with("❌ Leveling system is not available.")


@pytest.mark.asyncio
async def test_leaderboard_command_service_disabled() -> None:
    """Test leaderboard command when leveling service is disabled."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    
    leveling_service = MagicMock()
    leveling_service.is_enabled.return_value = False
    
    service_registry = MagicMock()
    service_registry.get_service.return_value = leveling_service
    
    context = MagicMock()
    context.bot_data = {'service_registry': service_registry}
    
    await utility_commands.leaderboard_command(update, context)
    
    update.message.reply_text.assert_awaited_once_with("❌ Leveling system is disabled.")


@pytest.mark.asyncio
async def test_leaderboard_command_invalid_limit() -> None:
    """Test leaderboard command with invalid limit argument."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    
    leveling_service = MagicMock()
    leveling_service.is_enabled.return_value = True
    
    service_registry = MagicMock()
    service_registry.get_service.return_value = leveling_service
    
    context = MagicMock()
    context.bot_data = {'service_registry': service_registry}
    context.args = ['invalid']
    
    await utility_commands.leaderboard_command(update, context)
    
    update.message.reply_text.assert_awaited_once_with("❌ Invalid limit. Please use a number (max 20).")


@pytest.mark.asyncio
async def test_leaderboard_command_no_data() -> None:
    """Test leaderboard command when no leaderboard data is available."""
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
    
    await utility_commands.leaderboard_command(update, context)
    
    leveling_service.get_leaderboard.assert_awaited_once_with(12345, 10)
    update.message.reply_text.assert_awaited_once_with("📊 No leaderboard data available yet.")


@pytest.mark.asyncio
async def test_leaderboard_command_success_default_limit() -> None:
    """Test successful leaderboard command with default limit."""
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
    
    achievement2 = Achievement(
        id="helpful",
        title="Helpful",
        description="Receive 5 thanks",
        emoji="🤝",
        sticker="🤝",
        condition_type="thanks",
        condition_value=5,
        category="social"
    )
    
    # Create mock user profiles
    profile1 = UserProfile(
        user_id=1001,
        username="user1",
        level=5,
        xp=1000,
        next_level_xp=1200,
        progress_percentage=83.3,
        achievements=[achievement1, achievement2],
        stats={"messages_count": 150, "links_shared": 10, "thanks_received": 8},
        rank=1
    )
    
    profile2 = UserProfile(
        user_id=1002,
        username="user2",
        level=3,
        xp=500,
        next_level_xp=600,
        progress_percentage=83.3,
        achievements=[achievement1],
        stats={"messages_count": 120, "links_shared": 5, "thanks_received": 3},
        rank=2
    )
    
    profile3 = UserProfile(
        user_id=1003,
        username=None,  # Test user without username
        level=2,
        xp=200,
        next_level_xp=300,
        progress_percentage=66.7,
        achievements=[],
        stats={"messages_count": 80, "links_shared": 2, "thanks_received": 1},
        rank=3
    )
    
    leaderboard = [profile1, profile2, profile3]
    
    leveling_service = MagicMock()
    leveling_service.is_enabled.return_value = True
    leveling_service.get_leaderboard = AsyncMock(return_value=leaderboard)
    
    service_registry = MagicMock()
    service_registry.get_service.return_value = leveling_service
    
    context = MagicMock()
    context.bot_data = {'service_registry': service_registry}
    context.args = []
    
    await utility_commands.leaderboard_command(update, context)
    
    leveling_service.get_leaderboard.assert_awaited_once_with(12345, 10)
    
    # Verify the message content
    call_args = update.message.reply_text.call_args
    message_text = call_args[0][0]
    
    assert "🏆 **Chat Leaderboard (Top 3)**" in message_text
    assert "🥇 **user1**" in message_text
    assert "Level 5 • 1,000 XP" in message_text
    assert "💬 🤝" in message_text  # Top achievements for rank 1
    assert "🥈 **user2**" in message_text
    assert "Level 3 • 500 XP" in message_text
    assert "🥉 **User 1003**" in message_text  # User without username
    assert "Level 2 • 200 XP" in message_text
    
    # Verify parse_mode is set to Markdown
    assert call_args[1]['parse_mode'] == 'Markdown'


@pytest.mark.asyncio
async def test_leaderboard_command_success_custom_limit() -> None:
    """Test successful leaderboard command with custom limit."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = 12345
    
    # Create a single mock user profile
    profile1 = UserProfile(
        user_id=1001,
        username="user1",
        level=5,
        xp=1000,
        next_level_xp=1200,
        progress_percentage=83.3,
        achievements=[],
        stats={"messages_count": 150, "links_shared": 10, "thanks_received": 8},
        rank=1
    )
    
    leaderboard = [profile1]
    
    leveling_service = MagicMock()
    leveling_service.is_enabled.return_value = True
    leveling_service.get_leaderboard = AsyncMock(return_value=leaderboard)
    
    service_registry = MagicMock()
    service_registry.get_service.return_value = leveling_service
    
    context = MagicMock()
    context.bot_data = {'service_registry': service_registry}
    context.args = ['5']
    
    await utility_commands.leaderboard_command(update, context)
    
    leveling_service.get_leaderboard.assert_awaited_once_with(12345, 5)
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_leaderboard_command_limit_capped_at_20() -> None:
    """Test leaderboard command with limit capped at maximum 20."""
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
    context.args = ['50']  # Request more than max
    
    await utility_commands.leaderboard_command(update, context)
    
    # Should be capped at 20
    leveling_service.get_leaderboard.assert_awaited_once_with(12345, 20)


@pytest.mark.asyncio
async def test_leaderboard_command_exception_handling() -> None:
    """Test leaderboard command exception handling."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = 12345
    
    leveling_service = MagicMock()
    leveling_service.is_enabled.return_value = True
    leveling_service.get_leaderboard = AsyncMock(side_effect=Exception("Database error"))
    
    service_registry = MagicMock()
    service_registry.get_service.return_value = leveling_service
    
    context = MagicMock()
    context.bot_data = {'service_registry': service_registry}
    context.args = []
    
    await utility_commands.leaderboard_command(update, context)
    
    update.message.reply_text.assert_awaited_once_with("❌ Error retrieving leaderboard. Please try again later.") 