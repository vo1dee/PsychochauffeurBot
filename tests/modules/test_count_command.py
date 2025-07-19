import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from modules.count_command import count_command, missing_command
import typing

class AsyncContextManagerMock:
    def __init__(self, value) -> None:
        self.value = value
    async def __aenter__(self) -> None:
        return self.value
    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

@pytest.mark.asyncio
async def test_count_command_missing_args() -> None:
    update = MagicMock()
    update.effective_chat.id = 1
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = []
    await count_command(update, context)
    update.message.reply_text.assert_awaited_once()
    assert "вкажіть одне слово" in update.message.reply_text.await_args[0][0]

@pytest.mark.asyncio
async def test_count_command_nonalpha_word() -> None:
    update = MagicMock()
    update.effective_chat.id = 1
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["1234!"]
    await count_command(update, context)
    update.message.reply_text.assert_awaited_once()
    assert "лише літери" in update.message.reply_text.await_args[0][0]

@pytest.mark.asyncio
async def test_count_command_db_error() -> None:
    update = MagicMock()
    update.effective_chat.id = 1
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["сонце"]
    with patch("modules.database.Database.get_pool", new=AsyncMock(side_effect=Exception("fail"))):
        with patch("modules.logger.error_logger.error") as mock_log:
            await count_command(update, context)
            update.message.reply_text.assert_awaited()
            mock_log.assert_called()
            assert "помилка" in update.message.reply_text.await_args[0][0]

@pytest.mark.asyncio
@pytest.mark.parametrize("count,expected", [
    (0, "не зустрічалося"),
    (1, "зустрілося 1 раз"),
    (5, "зустрілося 5 разів")
])
async def test_count_command_valid(count: int, expected: str) -> None:
    update = MagicMock()
    update.effective_chat.id = 1
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["сонце"]
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire = lambda: AsyncContextManagerMock(conn)
    conn.fetchval = AsyncMock(return_value=count)
    with patch("modules.database.Database.get_pool", new=AsyncMock(return_value=pool)):
        with patch("modules.logger.general_logger.info"):
            await count_command(update, context)
            update.message.reply_text.assert_awaited()
            assert expected in update.message.reply_text.await_args[0][0]

@pytest.mark.asyncio
async def test_missing_command_missing_args() -> None:
    update = MagicMock()
    update.effective_chat.id = 1
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = []
    await missing_command(update, context)
    update.message.reply_text.assert_awaited_once()
    assert "вкажіть username" in update.message.reply_text.await_args[0][0]

@pytest.mark.asyncio
async def test_missing_command_user_not_found_and_no_similar() -> None:
    update = MagicMock()
    update.effective_chat.id = 1
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["@user"]
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire = lambda: AsyncContextManagerMock(conn)
    conn.fetch = AsyncMock(side_effect=[[ ], [ ]])  # user_rows empty, similar_users empty
    with patch("modules.database.Database.get_pool", new=AsyncMock(return_value=pool)):
        with patch("modules.chat_analysis.get_last_message_for_user_in_chat", new=AsyncMock(return_value=None)):
            await missing_command(update, context)
            update.message.reply_text.assert_awaited()
            assert "не знайдено в базі даних" in update.message.reply_text.await_args[0][0]

@pytest.mark.asyncio
async def test_missing_command_user_not_found_but_similar() -> None:
    update = MagicMock()
    update.effective_chat.id = 1
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["@user"]
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire = lambda: AsyncContextManagerMock(conn)
    conn.fetch = AsyncMock(side_effect=[[ ], [{"username": "user1"}, {"username": "user2"}]])
    with patch("modules.database.Database.get_pool", new=AsyncMock(return_value=pool)):
        with patch("modules.chat_analysis.get_last_message_for_user_in_chat", new=AsyncMock(return_value=None)):
            await missing_command(update, context)
            update.message.reply_text.assert_awaited()
            assert "ви мали на увазі" in update.message.reply_text.await_args[0][0]

@pytest.mark.asyncio
async def test_missing_command_user_with_messages_in_other_chats() -> None:
    update = MagicMock()
    update.effective_chat.id = 1
    update.effective_chat.title = "Test Chat"
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["@user"]
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire = lambda: AsyncContextManagerMock(conn)
    conn.fetch = AsyncMock(side_effect=[[{"user_id": 1, "username": "user", "first_name": "A", "last_name": "B"}]])
    conn.fetchval = AsyncMock(return_value=3)
    with patch("modules.database.Database.get_pool", new=AsyncMock(return_value=pool)):
        with patch("modules.chat_analysis.get_last_message_for_user_in_chat", new=AsyncMock(return_value=None)):
            await missing_command(update, context)
            update.message.reply_text.assert_awaited()
            assert "інших чатах" in update.message.reply_text.await_args[0][0]

@pytest.mark.asyncio
async def test_missing_command_user_with_no_messages_anywhere() -> None:
    update = MagicMock()
    update.effective_chat.id = 1
    update.effective_chat.title = "Test Chat"
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["@user"]
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire = lambda: AsyncContextManagerMock(conn)
    conn.fetch = AsyncMock(side_effect=[[{"user_id": 1, "username": "user", "first_name": "A", "last_name": "B"}]])
    conn.fetchval = AsyncMock(return_value=0)
    with patch("modules.database.Database.get_pool", new=AsyncMock(return_value=pool)):
        with patch("modules.chat_analysis.get_last_message_for_user_in_chat", new=AsyncMock(return_value=None)):
            await missing_command(update, context)
            update.message.reply_text.assert_awaited()
            assert "жодному чаті" in update.message.reply_text.await_args[0][0]

@pytest.mark.asyncio
async def test_missing_command_valid_last_message() -> None:
    update = MagicMock()
    update.effective_chat.id = 1
    update.effective_chat.title = "Test Chat"
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["@user"]
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire = lambda: AsyncContextManagerMock(conn)
    conn.fetch = AsyncMock(side_effect=[[{"user_id": 1, "username": "user", "first_name": "A", "last_name": "B"}]])
    from datetime import datetime, timedelta
    import pytz
    now = datetime.now(pytz.UTC)
    last_message = (now - timedelta(hours=1), "user", "hello")
    with patch("modules.database.Database.get_pool", new=AsyncMock(return_value=pool)):
        with patch("modules.chat_analysis.get_last_message_for_user_in_chat", new=AsyncMock(return_value=last_message)):
            await missing_command(update, context)
            update.message.reply_text.assert_awaited()
            assert "востаннє писав" in update.message.reply_text.await_args[0][0] 