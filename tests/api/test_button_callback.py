import asyncio
import re
import pytest
from unittest.mock import AsyncMock, MagicMock

from modules.keyboards import button_callback, BUTTONS_CONFIG, LANGUAGE_OPTIONS_CONFIG

class DummyMessage:
    def __init__(self):
        self.edit_text = AsyncMock()
        self.chat_id = 1
        self.message_id = 1

class DummyQuery:
    def __init__(self, data):
        self.data = data
        self.answer = AsyncMock()
        self.message = DummyMessage()

class DummyUpdate:
    def __init__(self, data):
        self.callback_query = DummyQuery(data)

class DummyContext:
    def __init__(self):
        self.bot_data = {}

@pytest.mark.asyncio
@pytest.mark.parametrize("data,expected", [
    (None, "Invalid callback data."),
    ("", "Invalid callback data."),
    ("noColon", "Invalid callback data."),
])
async def test_button_invalid_format(data, expected):
    update = DummyUpdate(data)
    context = DummyContext()
    await button_callback(update, context)
    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.edit_text.assert_awaited_with(expected)

@pytest.mark.asyncio
async def test_button_unknown_action():
    # Use one hex hash for format
    data = "unknown:abcdef01"
    update = DummyUpdate(data)
    context = DummyContext()
    await button_callback(update, context)
    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.edit_text.assert_awaited_with("Unknown action.")

@pytest.mark.asyncio
async def test_button_invalid_hash():
    # Use valid action from BUTTONS_CONFIG
    action = BUTTONS_CONFIG[0]['action']
    data = f"{action}:ghij"
    update = DummyUpdate(data)
    context = DummyContext()
    await button_callback(update, context)
    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.edit_text.assert_awaited_with("Invalid callback identifier.")