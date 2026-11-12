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


@pytest.mark.asyncio
async def test_private_context_includes_failed_download_note(history):
    from modules.video_downloader import VideoDownloader

    link_update = make_update("https://youtube.com/shorts/abc", 1, chat_type="private")
    link_update.effective_chat.id = CHAT_ID
    add(history, 1, "https://youtube.com/shorts/abc")
    downloader = VideoDownloader.__new__(VideoDownloader)
    downloader.supported_platforms = []
    downloader.ERROR_STICKERS = ["sticker"]
    with patch("modules.error_handler.send_error_feedback", new=AsyncMock()):
        await downloader._handle_download_error(link_update, "https://youtube.com/shorts/abc")

    update = make_update("Ясно", 3, chat_type="private")
    messages = await get_context_messages(update, make_context(), "private")

    assert "Video download failed for https://youtube.com/shorts/abc" in messages[0]["content"]


@pytest.mark.asyncio
async def test_private_reply_always_gets_language_rule(history):
    from modules import gpt

    update = make_update("Ясно", 1, chat_type="private")
    update.message.reply_text = AsyncMock()
    complete = AsyncMock(return_value="Ок")
    with patch("modules.gpt.get_system_prompt", new=AsyncMock(return_value="You are a helpful assistant.")), \
            patch("modules.gpt._complete_with_tools", new=complete):
        await gpt.gpt_response(update, make_context(), response_type="private")

    system_prompt = complete.call_args.args[1][0]["content"]
    assert system_prompt.startswith("You are a helpful assistant.")
    assert gpt.LANGUAGE_RULE in system_prompt


@pytest.mark.asyncio
async def test_bare_ask_uses_latest_chat_messages(history):
    for i in range(1, 13):
        add(history, i, f"message {i}", author="Ivan")
    update = make_update("/ask", 13)

    messages = await get_context_messages(update, make_context(), "command", recent_chat=True)

    assert len(messages) == 1
    content = messages[0]["content"]
    assert messages[0]["role"] == "system"
    assert "Ivan: message 12" in content and "Ivan: message 3" in content
    assert "message 2\n" not in content and not content.endswith("message 2")


@pytest.mark.asyncio
async def test_ask_chat_tool_pages_back_ten_at_a_time():
    import json
    from modules.gpt import _ask_chat_tool_handler

    load_older = _ask_chat_tool_handler([f"m{i}" for i in range(25)])

    first = json.loads(await load_older({}))
    second = json.loads(await load_older({}))
    third = json.loads(await load_older({}))

    assert first == {"messages": [f"m{i}" for i in range(5, 15)], "has_more": True}
    assert second == {"messages": [f"m{i}" for i in range(0, 5)], "has_more": False}
    assert third == {"messages": [], "has_more": False}


def test_current_context_rule_states_real_date_and_asker():
    from datetime import datetime
    import pytz
    from modules.gpt import current_context_rule

    rule = current_context_rule(
        now=datetime(2026, 11, 12, 20, 50, tzinfo=pytz.utc), chat_title="Friends", author="Daria"
    )

    assert "Thursday, 12 November 2026, 22:50" in rule
    assert "UTC+02:00" in rule
    assert "Chat: Friends." in rule and "from: Daria." in rule


@pytest.mark.asyncio
async def test_ask_gets_date_context_and_web_search_tool(history):
    from modules import gpt

    update = make_update("/ask яке сьогодні свято?", 1)
    update.message.reply_text = AsyncMock()
    complete = AsyncMock(return_value="Ок")
    with patch("modules.gpt.get_system_prompt", new=AsyncMock(return_value="You are a helpful assistant.")), \
            patch("modules.gpt._complete_with_tools", new=complete):
        await gpt.gpt_response(update, make_context(), response_type="command")

    system_prompt = complete.call_args.args[1][0]["content"]
    assert "Current date and time:" in system_prompt
    assert gpt.WEB_SEARCH_TOOL_RULES in system_prompt
    assert gpt.WEB_SEARCH_TOOL_NAME in complete.call_args.args[4]


@pytest.mark.asyncio
async def test_web_search_returns_facts_snippets_and_pins_exa():
    import json
    from modules import web_search_tool

    create = AsyncMock(return_value={"choices": [{"message": {
        "content": "- Goes celebrates Sint-Maarten [omroepzeeland.nl, 12 Nov 2026]",
        "annotations": [
            {"type": "url_citation", "url_citation": {
                "url": "https://a.nl", "title": "A", "content": "Sint-Maarten  fireworks\n in Goes"}},
            {"type": "url_citation", "url_citation": {"url": "https://a.nl", "title": "A"}},
        ],
    }}]})
    handler = web_search_tool.make_web_search_handler()
    with patch("modules.gpt.OpenAIAsyncClient.Chat.Completions.create", new=create):
        result = json.loads(await handler(
            {"function": {"arguments": json.dumps({"query": "Goes fireworks", "deep": True})}}
        ))

    assert result["facts"].startswith("- Goes celebrates Sint-Maarten")
    assert result["sources"] == [{"title": "A", "url": "https://a.nl", "snippet": "Sint-Maarten fireworks in Goes"}]
    plugin = create.call_args.kwargs["plugins"][0]
    assert plugin["id"] == "web" and plugin["engine"] == "exa"
    assert plugin["mode"] == web_search_tool.WEB_SEARCH_DEEP_MODE
    assert create.call_args.kwargs["temperature"] == 0


@pytest.mark.asyncio
async def test_web_search_handler_enforces_per_request_budget():
    import json
    from modules import web_search_tool

    search = AsyncMock(return_value={"facts": "x", "sources": []})
    handler = web_search_tool.make_web_search_handler(max_searches=2)
    call = {"function": {"arguments": json.dumps({"query": "q"})}}
    with patch("modules.web_search_tool.web_search", new=search):
        results = [json.loads(await handler(call)) for _ in range(3)]

    assert search.await_count == 2
    assert "error" in results[2]
