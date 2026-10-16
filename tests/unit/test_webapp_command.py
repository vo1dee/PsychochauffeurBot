"""Tests for the /webapp demo command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.constants import ChatType

from modules.handlers.webapp_command import webapp_command


def _make_update(chat_type: str) -> MagicMock:
    update = MagicMock()
    update.effective_chat.type = chat_type
    update.message.reply_text = AsyncMock()
    return update


def _make_context() -> MagicMock:
    context = MagicMock()
    context.bot.username = "TestBot"
    return context


def _button(update: MagicMock):
    markup = update.message.reply_text.call_args.kwargs["reply_markup"]
    return markup.inline_keyboard[0][0]


@pytest.mark.asyncio
async def test_not_configured() -> None:
    update = _make_update(ChatType.PRIVATE)
    with patch.dict("os.environ", {"WEBAPP_URL": ""}):
        await webapp_command(update, _make_context())
    assert "WEBAPP_URL" in update.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_private_chat_uses_web_app_button() -> None:
    update = _make_update(ChatType.PRIVATE)
    with patch.dict("os.environ", {"WEBAPP_URL": "https://example.workers.dev/webapp"}):
        await webapp_command(update, _make_context())
    button = _button(update)
    assert button.web_app.url == "https://example.workers.dev/webapp"
    assert button.url is None


@pytest.mark.asyncio
async def test_group_uses_direct_link_when_short_name_set() -> None:
    update = _make_update(ChatType.SUPERGROUP)
    env = {"WEBAPP_URL": "https://example.workers.dev/webapp", "WEBAPP_SHORT_NAME": "weather"}
    with patch.dict("os.environ", env):
        await webapp_command(update, _make_context())
    button = _button(update)
    assert button.url == "https://t.me/TestBot/weather"
    assert button.web_app is None


@pytest.mark.asyncio
async def test_group_falls_back_to_private_chat_link() -> None:
    update = _make_update(ChatType.GROUP)
    env = {"WEBAPP_URL": "https://example.workers.dev/webapp", "WEBAPP_SHORT_NAME": ""}
    with patch.dict("os.environ", env):
        await webapp_command(update, _make_context())
    assert _button(update).url == "https://t.me/TestBot?start=webapp"
