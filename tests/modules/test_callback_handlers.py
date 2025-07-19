import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from modules.handlers import callback_handlers

@pytest.mark.asyncio
async def test_button_callback_delegates():
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.callback_handlers._button_callback", new=AsyncMock()) as mock_btn:
        await callback_handlers.button_callback(update, context)
        mock_btn.assert_awaited_once_with(update, context)

@pytest.mark.asyncio
async def test_speechrec_callback_invalid_prefix():
    update = MagicMock()
    query = update.callback_query
    query.data = "invalid_data"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    await callback_handlers.speechrec_callback(update, context)
    query.edit_message_text.assert_awaited()

@pytest.mark.asyncio
async def test_speechrec_callback_file_id_not_found():
    update = MagicMock()
    query = update.callback_query
    query.data = "speechrec_hash123"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    with patch("modules.handlers.callback_handlers.file_id_hash_map", {}):
        await callback_handlers.speechrec_callback(update, context)
        query.edit_message_text.assert_awaited()

@pytest.mark.asyncio
async def test_speechrec_callback_success():
    update = MagicMock()
    query = update.callback_query
    query.data = "speechrec_hash123"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    with patch("modules.handlers.callback_handlers.file_id_hash_map", {"hash123": "fileid"}):
        with patch("modules.handlers.callback_handlers.transcribe_telegram_voice", new=AsyncMock(return_value="transcript")):
            await callback_handlers.speechrec_callback(update, context)
            context.bot.send_message.assert_awaited()

@pytest.mark.asyncio
async def test_speechrec_callback_no_speech():
    update = MagicMock()
    query = update.callback_query
    query.data = "speechrec_hash123"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    with patch("modules.handlers.callback_handlers.file_id_hash_map", {"hash123": "fileid"}):
        with patch("modules.handlers.callback_handlers.transcribe_telegram_voice", new=AsyncMock(side_effect=callback_handlers.SpeechmaticsNoSpeechDetected)):
            await callback_handlers.speechrec_callback(update, context)
            context.bot.send_message.assert_awaited()

@pytest.mark.asyncio
async def test_speechrec_callback_language_not_expected():
    update = MagicMock()
    query = update.callback_query
    query.data = "speechrec_hash123"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    with patch("modules.handlers.callback_handlers.file_id_hash_map", {"hash123": "fileid"}):
        with patch("modules.handlers.callback_handlers.transcribe_telegram_voice", new=AsyncMock(side_effect=callback_handlers.SpeechmaticsLanguageNotExpected)), \
             patch("modules.handlers.callback_handlers.HashGenerator.file_id_hash", return_value="hash123"), \
             patch("modules.handlers.callback_handlers.get_language_keyboard", return_value="keyboard"):
            await callback_handlers.speechrec_callback(update, context)
            context.bot.send_message.assert_awaited()

@pytest.mark.asyncio
async def test_speechrec_callback_generic_exception():
    update = MagicMock()
    query = update.callback_query
    query.data = "speechrec_hash123"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    with patch("modules.handlers.callback_handlers.file_id_hash_map", {"hash123": "fileid"}):
        with patch("modules.handlers.callback_handlers.transcribe_telegram_voice", new=AsyncMock(side_effect=Exception("fail"))):
            await callback_handlers.speechrec_callback(update, context)
            context.bot.send_message.assert_awaited()

@pytest.mark.asyncio
async def test_language_selection_callback_test_callback():
    update = MagicMock()
    query = update.callback_query
    query.data = "test_callback"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    await callback_handlers.language_selection_callback(update, context)
    query.edit_message_text.assert_awaited_with("✅ Test callback received and handled!")

@pytest.mark.asyncio
async def test_language_selection_callback_invalid_data():
    update = MagicMock()
    query = update.callback_query
    query.data = "invalid"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    await callback_handlers.language_selection_callback(update, context)
    query.edit_message_text.assert_awaited()

@pytest.mark.asyncio
async def test_language_selection_callback_success():
    update = MagicMock()
    query = update.callback_query
    query.data = "lang_en|hash123"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    with patch("modules.handlers.callback_handlers.file_id_hash_map", {"hash123": "fileid"}), \
         patch("modules.handlers.callback_handlers.HashGenerator.file_id_hash", return_value="hash123"), \
         patch("modules.handlers.callback_handlers.get_language_keyboard", return_value="keyboard"), \
         patch("modules.handlers.callback_handlers.transcribe_telegram_voice", new=AsyncMock(return_value="transcript")):
        await callback_handlers.language_selection_callback(update, context)
        query.edit_message_text.assert_awaited()

@pytest.mark.asyncio
async def test_language_selection_callback_language_not_expected():
    update = MagicMock()
    query = update.callback_query
    query.data = "lang_en|hash123"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    with patch("modules.handlers.callback_handlers.file_id_hash_map", {"hash123": "fileid"}), \
         patch("modules.handlers.callback_handlers.HashGenerator.file_id_hash", return_value="hash123"), \
         patch("modules.handlers.callback_handlers.get_language_keyboard", return_value="keyboard"), \
         patch("modules.handlers.callback_handlers.transcribe_telegram_voice", new=AsyncMock(side_effect=callback_handlers.SpeechmaticsLanguageNotExpected)):
        await callback_handlers.language_selection_callback(update, context)
        query.edit_message_text.assert_awaited()

@pytest.mark.asyncio
async def test_language_selection_callback_generic_exception():
    update = MagicMock()
    query = update.callback_query
    query.data = "lang_en|hash123"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    context = MagicMock()
    with patch("modules.handlers.callback_handlers.file_id_hash_map", {"hash123": "fileid"}), \
         patch("modules.handlers.callback_handlers.HashGenerator.file_id_hash", return_value="hash123"), \
         patch("modules.handlers.callback_handlers.get_language_keyboard", return_value="keyboard"), \
         patch("modules.handlers.callback_handlers.transcribe_telegram_voice", new=AsyncMock(side_effect=Exception("fail"))):
        await callback_handlers.language_selection_callback(update, context)
        query.edit_message_text.assert_awaited() 