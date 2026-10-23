"""Tests for /ask (concise, no chat context) vs mention/reply (threaded conversation) context."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.gpt import get_context_messages
from modules.message_processor import needs_gpt_response
from modules.utils import ChatHistoryManager

BOT_ID = 999
CHAT_ID = -100


def make_update(text, message_id, reply_to=None, chat_type="supergroup"):
    update = MagicMock()
    update.effective_chat.id = CHAT_ID
    update.effective_chat.type = chat_type
    update.effective_chat.title = "Test chat"
    update.message.text = text
    update.message.message_id = message_id
    update.message.reply_to_message = reply_to
    return update


def make_reply(message_id, text, from_id):
    reply = MagicMock()
    reply.message_id = message_id
    reply.text = text
    reply.caption = None
    reply.from_user.id = from_id
    reply.from_user.first_name = "Bot" if from_id == BOT_ID else "Olena"
    return reply


def make_context():
    context = MagicMock()
    context.bot.id = BOT_ID
    context.bot.username = "TestBot"
    return context


@pytest.fixture
def history():
    manager = ChatHistoryManager()
    config_manager = MagicMock()
    config_manager.get_config = AsyncMock(return_value={"config_modules": {"gpt": {"context_messages_count": 2}}})
    with patch("modules.utils.chat_history_manager", manager), \
            patch("modules.gpt.get_shared_config_manager", return_value=config_manager):
        yield manager


def add(manager, message_id, text, is_user=True, reply_to=None, author="Olena", is_gpt=False):
    manager.add_message(CHAT_ID, {
        "text": text, "is_user": is_user, "author": author if is_user else None,
        "message_id": message_id, "reply_to_message_id": reply_to, "is_gpt": is_gpt,
    })


@pytest.mark.asyncio
async def test_ask_ignores_chat_history(history):
    add(history, 1, "unrelated chatter")
    update = make_update("/ask what is 2+2", 2)

    assert await get_context_messages(update, make_context(), "command") == []


@pytest.mark.asyncio
async def test_ask_includes_replied_message(history):
    update = make_update("/ask translate this", 2, reply_to=make_reply(1, "bonjour", from_id=5))

    messages = await get_context_messages(update, make_context(), "command")

    assert len(messages) == 1
    assert "bonjour" in messages[0]["content"]


@pytest.mark.asyncio
async def test_mention_follows_reply_thread(history):
    add(history, 1, "noise before")
    add(history, 2, "@TestBot what is the capital of France?", author="Olena")
    add(history, 3, "Paris.", is_user=False, reply_to=2, is_gpt=True)
    add(history, 4, "noise in between", author="Ivan")
    add(history, 5, "and its population?", reply_to=3, author="Olena")
    update = make_update("and its population?", 5, reply_to=make_reply(3, "Paris.", from_id=BOT_ID))

    messages = await get_context_messages(update, make_context(), "mention")

    background, *thread = messages
    assert background["role"] == "system"
    assert "noise in between" in background["content"]
    assert "Paris." not in background["content"]
    assert thread == [
        {"role": "user", "content": "Olena: what is the capital of France?"},
        {"role": "assistant", "content": "Paris."},
    ]


@pytest.mark.asyncio
async def test_mention_uses_telegram_reply_when_not_in_history(history):
    update = make_update("why?", 10, reply_to=make_reply(9, "Because.", from_id=BOT_ID))

    messages = await get_context_messages(update, make_context(), "mention")

    assert messages == [{"role": "assistant", "content": "Because."}]


def test_reply_to_bot_gpt_answer_triggers_conversation(history):
    add(history, 3, "Paris.", is_user=False, is_gpt=True)
    update = make_update("and its population?", 5, reply_to=make_reply(3, "Paris.", from_id=BOT_ID))

    assert needs_gpt_response(update, make_context(), "and its population?") == (True, "mention")


def test_reply_to_non_gpt_bot_message_is_ignored(history):
    add(history, 3, "Modified link", is_user=False)
    update = make_update("thanks", 5, reply_to=make_reply(3, "Modified link", from_id=BOT_ID))

    assert needs_gpt_response(update, make_context(), "thanks") == (False, "")
