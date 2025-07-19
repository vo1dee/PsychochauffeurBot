import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from modules.handlers import message_handlers

@pytest.mark.asyncio
async def test_handle_message_command_ignored():
    update = MagicMock()
    update.message.text = "/start"
    context = MagicMock()
    await message_handlers.handle_message(update, context)  # Should return early, nothing called

@pytest.mark.asyncio
async def test_handle_message_translation_command():
    update = MagicMock()
    update.message.text = "бля!"
    update.message.from_user.id = 1
    context = MagicMock()
    with patch("modules.handlers.message_handlers._handle_translation_command", new=AsyncMock()) as mock_trans, \
         patch("modules.handlers.message_handlers.service_registry.get_service", return_value=MagicMock()):
        await message_handlers.handle_message(update, context)
        mock_trans.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_message_restriction():
    update = MagicMock()
    update.message.text = "Ы forbidden"
    update.message.from_user.id = 1
    context = MagicMock()
    with patch("modules.handlers.message_handlers.restrict_user", new=AsyncMock()) as mock_restrict, \
         patch("modules.handlers.message_handlers.service_registry.get_service", return_value=MagicMock()):
        await message_handlers.handle_message(update, context)
        mock_restrict.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_message_gpt_response():
    update = MagicMock()
    update.message.text = "hello bot"
    update.message.from_user.id = 1
    context = MagicMock()
    with patch("modules.handlers.message_handlers.needs_gpt_response", return_value=(True, "mention")), \
         patch("modules.handlers.message_handlers.gpt_response", new=AsyncMock()) as mock_gpt, \
         patch("modules.handlers.message_handlers.service_registry.get_service", return_value=MagicMock()):
        await message_handlers.handle_message(update, context)
        mock_gpt.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_message_random_gpt():
    update = MagicMock()
    update.message.text = "random text"
    update.message.from_user.id = 1
    context = MagicMock()
    with patch("modules.handlers.message_handlers.needs_gpt_response", return_value=(False, "")), \
         patch("modules.handlers.message_handlers.TelegramHelpers.is_group_chat", return_value=True), \
         patch("modules.handlers.message_handlers.handle_random_gpt_response", new=AsyncMock()) as mock_rand, \
         patch("modules.handlers.message_handlers.service_registry.get_service", return_value=MagicMock()):
        await message_handlers.handle_message(update, context)
        mock_rand.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_message_modified_links():
    update = MagicMock()
    update.message.text = "check this link"
    update.message.from_user.id = 1
    context = MagicMock()
    with patch("modules.handlers.message_handlers.needs_gpt_response", return_value=(False, "")), \
         patch("modules.handlers.message_handlers.TelegramHelpers.is_group_chat", return_value=False), \
         patch("modules.handlers.message_handlers.process_message_content", return_value=("cleaned", ["http://example.com"])), \
         patch("modules.handlers.message_handlers.process_urls", new=AsyncMock()) as mock_urls, \
         patch("modules.handlers.message_handlers.service_registry.get_service", return_value=MagicMock()):
        await message_handlers.handle_message(update, context)
        mock_urls.assert_awaited_once()

@pytest.mark.asyncio
async def test__handle_translation_command_no_previous():
    update = MagicMock()
    update.message.from_user.username = "user"
    update.message.reply_text = AsyncMock()
    user_id = 1
    with patch("modules.handlers.message_handlers.get_previous_message", return_value=None):
        await message_handlers._handle_translation_command(update, user_id)
        update.message.reply_text.assert_awaited_with("Немає попереднього повідомлення для перекладу.")

@pytest.mark.asyncio
async def test__handle_translation_command_success():
    update = MagicMock()
    update.message.from_user.username = "user"
    update.message.reply_text = AsyncMock()
    user_id = 1
    with patch("modules.handlers.message_handlers.get_previous_message", return_value="prev"), \
         patch("modules.keyboard_translator.auto_translate_text", return_value="translated"):
        await message_handlers._handle_translation_command(update, user_id)
        update.message.reply_text.assert_awaited()

@pytest.mark.asyncio
async def test_process_urls_calls_construct_and_send_message():
    update = MagicMock()
    update.effective_chat.id = 1
    update.message.from_user.username = "user"
    context = MagicMock()
    with patch("modules.handlers.message_handlers.construct_and_send_message", new=AsyncMock()) as mock_send:
        await message_handlers.process_urls(update, context, ["http://example.com"], "msg")
        mock_send.assert_awaited_once() 