"""Tests for the /recap command handler."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from modules.handlers import recap_commands


def _make_update_context(args):
    update = MagicMock()
    update.effective_chat.id = -100123
    update.effective_chat.type = "group"
    update.effective_user.id = 2
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = args
    return update, context


@pytest.mark.asyncio
async def test_recap_on_default_time() -> None:
    update, context = _make_update_context(["on"])
    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)), \
         patch.object(recap_commands.Database, "upsert_recap_settings", new=AsyncMock()) as mock_upsert:
        await recap_commands.recap_command(update, context)

    mock_upsert.assert_awaited_once_with(-100123, enabled=True, send_time=None)
    update.message.reply_text.assert_awaited_once()
    assert "09:30" in update.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_recap_on_with_custom_time() -> None:
    update, context = _make_update_context(["on", "10:15"])
    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)), \
         patch.object(recap_commands.Database, "upsert_recap_settings", new=AsyncMock()) as mock_upsert:
        await recap_commands.recap_command(update, context)

    mock_upsert.assert_awaited_once_with(-100123, enabled=True, send_time="10:15")
    assert "10:15" in update.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_recap_on_with_invalid_time() -> None:
    update, context = _make_update_context(["on", "25:99"])
    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)), \
         patch.object(recap_commands.Database, "upsert_recap_settings", new=AsyncMock()) as mock_upsert:
        await recap_commands.recap_command(update, context)

    mock_upsert.assert_not_called()
    assert "❌" in update.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_recap_off() -> None:
    update, context = _make_update_context(["off"])
    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)), \
         patch.object(recap_commands.Database, "upsert_recap_settings", new=AsyncMock()) as mock_upsert:
        await recap_commands.recap_command(update, context)

    mock_upsert.assert_awaited_once_with(-100123, enabled=False)
    update.message.reply_text.assert_awaited_once_with("🔕 Щоденний рекап вимкнено.")


@pytest.mark.asyncio
async def test_recap_time_valid() -> None:
    update, context = _make_update_context(["time", "08:00"])
    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)), \
         patch.object(recap_commands.Database, "upsert_recap_settings", new=AsyncMock()) as mock_upsert:
        await recap_commands.recap_command(update, context)

    mock_upsert.assert_awaited_once_with(-100123, send_time="08:00")
    assert "08:00" in update.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_recap_time_missing_arg() -> None:
    update, context = _make_update_context(["time"])
    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)), \
         patch.object(recap_commands.Database, "upsert_recap_settings", new=AsyncMock()) as mock_upsert:
        await recap_commands.recap_command(update, context)

    mock_upsert.assert_not_called()


@pytest.mark.asyncio
async def test_recap_status_enabled() -> None:
    update, context = _make_update_context([])
    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)), \
         patch.object(recap_commands.Database, "get_recap_settings", new=AsyncMock(
             return_value={"enabled": True, "send_time": "09:30"}
         )):
        await recap_commands.recap_command(update, context)

    reply = update.message.reply_text.call_args.args[0]
    assert "увімкнено" in reply
    assert "09:30" in reply
    # 'now' must never appear in user-visible usage text.
    assert "/recap now" not in reply


@pytest.mark.asyncio
async def test_recap_status_disabled_by_default() -> None:
    update, context = _make_update_context([])
    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)), \
         patch.object(recap_commands.Database, "get_recap_settings", new=AsyncMock(return_value=None)):
        await recap_commands.recap_command(update, context)

    reply = update.message.reply_text.call_args.args[0]
    assert "вимкнено" in reply


@pytest.mark.asyncio
async def test_recap_non_admin_blocked() -> None:
    update, context = _make_update_context(["on"])
    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=False)), \
         patch.object(recap_commands.Database, "upsert_recap_settings", new=AsyncMock()) as mock_upsert:
        await recap_commands.recap_command(update, context)

    mock_upsert.assert_not_called()
    assert "адмін" in update.message.reply_text.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_recap_unknown_subcommand_shows_usage() -> None:
    update, context = _make_update_context(["frobnicate"])
    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)):
        await recap_commands.recap_command(update, context)

    reply = update.message.reply_text.call_args.args[0]
    assert reply == recap_commands.USAGE_TEXT
    assert "now" not in reply


@pytest.mark.asyncio
async def test_recap_now_generates_and_sends() -> None:
    update, context = _make_update_context(["now"])
    status_message = MagicMock()
    status_message.edit_text = AsyncMock()
    status_message.delete = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=status_message)

    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)), \
         patch.object(recap_commands, "generate_recap", new=AsyncMock(return_value="the recap body")) as mock_generate, \
         patch.object(recap_commands, "send_recap", new=AsyncMock()) as mock_send:
        await recap_commands.recap_command(update, context)

    assert mock_generate.await_args.args[0] == -100123
    assert mock_generate.await_args.kwargs.get("min_messages") == 1
    status_message.delete.assert_awaited_once()
    mock_send.assert_awaited_once_with(context.bot, -100123, "the recap body")


@pytest.mark.asyncio
async def test_recap_now_no_messages() -> None:
    update, context = _make_update_context(["now"])
    status_message = MagicMock()
    status_message.edit_text = AsyncMock()
    status_message.delete = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=status_message)

    with patch("modules.handlers.recap_commands.is_admin", new=AsyncMock(return_value=True)), \
         patch.object(recap_commands, "generate_recap", new=AsyncMock(return_value=None)), \
         patch.object(recap_commands, "send_recap", new=AsyncMock()) as mock_send:
        await recap_commands.recap_command(update, context)

    status_message.edit_text.assert_awaited_once()
    mock_send.assert_not_called()
