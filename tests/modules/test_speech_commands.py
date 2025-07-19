import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from modules.handlers import speech_commands

@pytest.mark.asyncio
async def test_speech_command_admin_on():
    update = MagicMock()
    update.effective_chat.id = 1
    update.effective_chat.type = "group"
    update.effective_user.id = 2
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["on"]
    config_manager = AsyncMock()
    config_manager.get_config = AsyncMock(return_value={"config_modules": {"speechmatics": {"overrides": {"allow_all_users": False}}}})
    config_manager.update_module_setting = AsyncMock()
    with patch("modules.handlers.speech_commands.service_registry.get_service", return_value=config_manager), \
         patch("modules.handlers.speech_commands.is_admin", new=AsyncMock(return_value=True)):
        await speech_commands.speech_command(update, context)
        update.message.reply_text.assert_awaited_with("Speech recognition enabled.")

@pytest.mark.asyncio
async def test_speech_command_non_admin():
    update = MagicMock()
    update.effective_chat.id = 1
    update.effective_chat.type = "group"
    update.effective_user.id = 2
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["on"]
    config_manager = AsyncMock()
    config_manager.get_config = AsyncMock(return_value={"config_modules": {"speechmatics": {"overrides": {"allow_all_users": False}}}})
    with patch("modules.handlers.speech_commands.service_registry.get_service", return_value=config_manager), \
         patch("modules.handlers.speech_commands.is_admin", new=AsyncMock(return_value=False)):
        await speech_commands.speech_command(update, context)
        update.message.reply_text.assert_awaited_with("❌ Only admins can use this command.")

@pytest.mark.asyncio
async def test_speech_command_invalid_args():
    update = MagicMock()
    update.effective_chat.id = 1
    update.effective_chat.type = "group"
    update.effective_user.id = 2
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["maybe"]
    config_manager = AsyncMock()
    config_manager.get_config = AsyncMock(return_value={"config_modules": {"speechmatics": {"overrides": {"allow_all_users": True}}}})
    with patch("modules.handlers.speech_commands.service_registry.get_service", return_value=config_manager), \
         patch("modules.handlers.speech_commands.is_admin", new=AsyncMock(return_value=True)):
        await speech_commands.speech_command(update, context)
        update.message.reply_text.assert_awaited_with("Usage: /speech on|off")

@pytest.mark.asyncio
async def test_speech_command_config_update():
    update = MagicMock()
    update.effective_chat.id = 1
    update.effective_chat.type = "group"
    update.effective_user.id = 2
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["off"]
    config_manager = AsyncMock()
    config_manager.get_config = AsyncMock(return_value={"config_modules": {}})
    config_manager.save_config = AsyncMock()
    config_manager.update_module_setting = AsyncMock()
    with patch("modules.handlers.speech_commands.service_registry.get_service", return_value=config_manager), \
         patch("modules.handlers.speech_commands.is_admin", new=AsyncMock(return_value=True)):
        await speech_commands.speech_command(update, context)
        update.message.reply_text.assert_awaited_with("Speech recognition disabled.")

@pytest.mark.asyncio
async def test_get_speech_config():
    config_manager = AsyncMock()
    config_manager.get_config = AsyncMock(return_value={"config_modules": {"speechmatics": {"foo": "bar"}}})
    result = await speech_commands.get_speech_config("1", "group", config_manager)
    assert result == {"foo": "bar"}

@pytest.mark.asyncio
async def test_is_admin_private():
    update = MagicMock()
    update.effective_chat.type = "private"
    context = MagicMock()
    result = await speech_commands.is_admin(update, context)
    assert result is True

@pytest.mark.asyncio
async def test_is_admin_group_admin():
    update = MagicMock()
    update.effective_chat.type = "group"
    update.effective_chat.id = 1
    update.effective_user.id = 2
    context = MagicMock()
    context.bot.get_chat_member = AsyncMock(return_value=MagicMock(status="administrator"))
    result = await speech_commands.is_admin(update, context)
    assert result is True

@pytest.mark.asyncio
async def test_is_admin_group_non_admin():
    update = MagicMock()
    update.effective_chat.type = "group"
    update.effective_chat.id = 1
    update.effective_user.id = 2
    context = MagicMock()
    context.bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
    result = await speech_commands.is_admin(update, context)
    assert result is False

@pytest.mark.asyncio
async def test_is_admin_group_exception():
    update = MagicMock()
    update.effective_chat.type = "group"
    update.effective_chat.id = 1
    update.effective_user.id = 2
    context = MagicMock()
    context.bot.get_chat_member = AsyncMock(side_effect=Exception("fail"))
    result = await speech_commands.is_admin(update, context)
    assert result is False 